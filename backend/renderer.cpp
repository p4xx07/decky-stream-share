// Stream Share overlay renderer. It never changes Gamescope or Steam settings.
#include "media_bridge.h"
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/shape.h>
#include <X11/extensions/Xrender.h>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <csignal>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <sys/types.h>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <unistd.h>

namespace {
constexpr int kCaptureWidth = 640;
constexpr int kCaptureHeight = 400;
constexpr int kCaptureBytes = kCaptureWidth * kCaptureHeight * 4;
std::atomic<bool> running{true};

void handle_signal(int) { running = false; }

struct Capture {
    pid_t pid = -1;
    int fd = -1;
    std::atomic<bool> done{false};
    std::atomic<unsigned long> frames{0};
    std::mutex mutex;
    std::condition_variable updated;
    std::vector<unsigned char> latest;
    std::thread reader;
};

bool read_frame(int fd, std::vector<unsigned char> &frame) {
    size_t offset = 0;
    while (offset < frame.size() && running) {
        ssize_t count = read(fd, frame.data() + offset, frame.size() - offset);
        if (count == 0) return false;
        if (count < 0) {
            if (errno == EINTR) continue;
            return false;
        }
        offset += static_cast<size_t>(count);
    }
    return offset == frame.size();
}

bool start_capture(Capture &capture, bool synthetic, bool direct, int display_width,
                   int display_height, int crop_left, int crop_top,
                   int crop_width, int crop_height, MediaBridge *bridge) {
    int pipefd[2];
    if (pipe(pipefd) != 0) return false;
    capture.pid = fork();
    if (capture.pid < 0) {
        close(pipefd[0]);
        close(pipefd[1]);
        return false;
    }
    if (capture.pid == 0) {
        dup2(pipefd[1], STDOUT_FILENO);
        close(pipefd[0]);
        close(pipefd[1]);
        if (synthetic) {
            execlp("gst-launch-1.0", "gst-launch-1.0", "-q", "videotestsrc", "is-live=true",
                   "!", "videoconvert", "!", "videoscale", "!", "videorate",
                   "drop-only=true", "!",
                   "video/x-raw,format=BGRx,width=640,height=400,framerate=30/1", "!",
                   "fdsink", "fd=1", "sync=false", static_cast<char *>(nullptr));
        } else {
            std::vector<std::string> args = {
                "gst-launch-1.0", "-q", "pipewiresrc", "target-object=gamescope",
                "do-timestamp=true", "!", "queue", "leaky=downstream",
                "max-size-buffers=1", "!", "videoconvert", "!", "videoscale", "!"};
            if (direct) {
                args.push_back("video/x-raw,format=BGRx,width=" + std::to_string(display_width) +
                               ",height=" + std::to_string(display_height));
                args.insert(args.end(), {"!", "videocrop",
                    "left=" + std::to_string(crop_left),
                    "top=" + std::to_string(crop_top),
                    "right=" + std::to_string(display_width - crop_left - crop_width),
                    "bottom=" + std::to_string(display_height - crop_top - crop_height),
                    "!", "videoscale", "add-borders=true", "!"});
            }
            args.insert(args.end(), {"videorate", "drop-only=true", "!",
                "video/x-raw,format=BGRx,width=640,height=400,framerate=30/1",
                "!", "fdsink", "fd=1", "sync=false"});
            std::vector<char *> argv;
            for (auto &arg : args) argv.push_back(arg.data());
            argv.push_back(nullptr);
            execvp(argv[0], argv.data());
        }
        std::perror("Could not start gst-launch-1.0");
        _exit(127);
    }
    close(pipefd[1]);
    capture.fd = pipefd[0];
    capture.reader = std::thread([&capture, bridge, direct] {
        std::vector<unsigned char> frame(kCaptureBytes);
        auto next_share = std::chrono::steady_clock::now();
        while (read_frame(capture.fd, frame)) {
            const auto now = std::chrono::steady_clock::now();
            if (bridge && now >= next_share) {
                bridge->submit(frame);
                next_share = now + std::chrono::milliseconds(100);
            }
            unsigned long count;
            {
                std::lock_guard<std::mutex> lock(capture.mutex);
                // Keep the read buffer allocated for the next full frame. Swapping
                // leaves it empty, so the next read appears to succeed immediately
                // and clears the local image before the display loop can use it.
                if (!direct) capture.latest = frame;
                count = ++capture.frames;
            }
            capture.updated.notify_one();
            if (count == 1 || count % 75 == 0) {
                std::fprintf(stderr, "Captured %lu frames\n", count);
                std::fflush(stderr);
            }
        }
        capture.done = true;
        capture.updated.notify_one();
    });
    return true;
}

void stop_capture(Capture &capture) {
    if (capture.pid > 0) {
        kill(capture.pid, SIGTERM);
        for (int attempt = 0; attempt < 20; ++attempt) {
            if (waitpid(capture.pid, nullptr, WNOHANG) == capture.pid) break;
            if (attempt == 19) {
                kill(capture.pid, SIGKILL);
                waitpid(capture.pid, nullptr, 0);
            } else {
                std::this_thread::sleep_for(std::chrono::milliseconds(50));
            }
        }
    }
    if (capture.reader.joinable()) capture.reader.join();
    if (capture.fd >= 0) close(capture.fd);
}

struct Rect {
    int x;
    int y;
    int width;
    int height;
};

void render(XImage *image, const std::vector<unsigned char> &frame,
            const std::vector<unsigned char> &remote, bool pattern,
            bool direct, const Rect &game, const Rect &friend_view) {
    const int width = image->width;
    const int height = image->height;
    const int fitted_width = std::min(game.width, game.height * kCaptureWidth / kCaptureHeight);
    const int fitted_height = std::min(game.height, fitted_width * kCaptureHeight / kCaptureWidth);
    const int fitted_x = game.x + (game.width - fitted_width) / 2;
    const int fitted_y = game.y + (game.height - fitted_height) / 2;

    for (int y = 0; y < height; ++y) {
        auto *row = reinterpret_cast<uint32_t *>(image->data + y * image->bytes_per_line);
        std::fill_n(row, width, direct ? 0x00000000 : 0xff000000);
        if (direct && y >= friend_view.y && y < friend_view.y + friend_view.height)
            std::fill_n(row + friend_view.x, friend_view.width, 0xff000000);
    }
    if (!direct && (!frame.empty() || pattern)) {
        for (int y = 0; y < fitted_height; ++y) {
            auto *row = reinterpret_cast<uint32_t *>(image->data + (fitted_y + y) * image->bytes_per_line);
            const int source_y = y * kCaptureHeight / fitted_height;
            for (int x = 0; x < fitted_width; ++x) {
                if (pattern) {
                    const int stripe = (x * 6 / fitted_width);
                    constexpr uint32_t colors[] = {0x00e53935, 0x00fdd835, 0x0043a047,
                                                    0x001e88e5, 0x008e24aa, 0x00f5f5f5};
                    row[fitted_x + x] = 0xff000000 | colors[stripe];
                } else {
                    const int source_x = x * kCaptureWidth / fitted_width;
                    const auto *source = frame.data() + (source_y * kCaptureWidth + source_x) * 4;
                    row[fitted_x + x] = 0xff000000 | uint32_t(source[0]) | (uint32_t(source[1]) << 8) |
                                      (uint32_t(source[2]) << 16);
                }
            }
        }
    }
    if (!remote.empty()) {
        const int friend_width = std::min(friend_view.width,
                                          friend_view.height * kCaptureWidth / kCaptureHeight);
        const int friend_height = std::min(friend_view.height,
                                           friend_width * kCaptureHeight / kCaptureWidth);
        const int friend_x = friend_view.x + (friend_view.width - friend_width) / 2;
        const int friend_y = friend_view.y + (friend_view.height - friend_height) / 2;
        for (int y = 0; y < friend_height; ++y) {
            auto *row = reinterpret_cast<uint32_t *>(image->data + (friend_y + y) * image->bytes_per_line);
            const int source_y = y * kCaptureHeight / friend_height;
            for (int x = 0; x < friend_width; ++x) {
                const int source_x = x * kCaptureWidth / friend_width;
                const auto *source = remote.data() + (source_y * kCaptureWidth + source_x) * 4;
                row[friend_x + x] = 0xff000000 | uint32_t(source[0]) | (uint32_t(source[1]) << 8) |
                                    (uint32_t(source[2]) << 16);
            }
        }
    }
}
} // namespace

int main(int argc, char **argv) {
    if ((argc != 5 && argc != 7) || std::strcmp(argv[1], "--mode") != 0 ||
        std::strcmp(argv[3], "--layout") != 0 ||
        (argc == 7 && std::strcmp(argv[5], "--ipc") != 0)) {
        std::fprintf(stderr, "Usage: stream-share-renderer --mode pattern|synthetic|live|direct|direct-test|direct-pattern --layout side|wide|stack|full [--ipc socket]\n");
        return 2;
    }
    const std::string mode(argv[2]);
    if (mode != "pattern" && mode != "synthetic" && mode != "live" &&
        mode != "direct" && mode != "direct-test" && mode != "direct-pattern") return 2;
    const bool direct = mode == "direct" || mode == "direct-test" || mode == "direct-pattern";
    const std::string layout(argv[4]);
    if (layout != "side" && layout != "wide" && layout != "stack" && layout != "full") return 2;
    const std::string ipc_path = argc == 7 ? argv[6] : "";
    // An orphaned full-screen layer would be difficult to dismiss in Gaming Mode.
    const pid_t parent = getppid();
    if (prctl(PR_SET_PDEATHSIG, SIGTERM) != 0 || getppid() != parent) return 8;
    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);
    std::signal(SIGPIPE, SIG_IGN);

    Display *display = XOpenDisplay(nullptr);
    if (!display) {
        std::fprintf(stderr, "Cannot connect to Gamescope X display. Check DISPLAY.\n");
        return 3;
    }
    const int screen = DefaultScreen(display);
    const int width = DisplayWidth(display, screen);
    const int height = DisplayHeight(display, screen);
    if (width < 2 || height < 2) {
        std::fprintf(stderr, "Display is too small for split view.\n");
        XCloseDisplay(display);
        return 4;
    }
    Rect game{};
    Rect friend_view{};
    if (layout == "full") {
        game = {0, 0, width, height};
        friend_view = {0, 0, 0, 0};
    } else if (layout == "stack") {
        game = {0, 0, width, height / 2};
        friend_view = {0, height / 2, width, height - height / 2};
    } else {
        const int game_width = layout == "wide" ? width * 2 / 3 : width / 2;
        game = {0, 0, game_width, height};
        friend_view = {game_width, 0, width - game_width, height};
    }
    Visual *visual = DefaultVisual(display, screen);
    int depth = DefaultDepth(display, screen);
    if (direct) {
        XVisualInfo visual_info{};
        if (!XMatchVisualInfo(display, screen, 32, TrueColor, &visual_info) ||
            !XRenderFindVisualFormat(display, visual_info.visual) ||
            XRenderFindVisualFormat(display, visual_info.visual)->direct.alphaMask == 0) {
            std::fprintf(stderr, "Gamescope X display has no ARGB visual; direct mode unavailable.\n");
            XCloseDisplay(display);
            return 4;
        }
        visual = visual_info.visual;
        depth = visual_info.depth;
    }
    if (visual->red_mask != 0x00ff0000 || visual->green_mask != 0x0000ff00 ||
        visual->blue_mask != 0x000000ff) {
        std::fprintf(stderr, "Unsupported X11 pixel format for the split view.\n");
        XCloseDisplay(display);
        return 4;
    }

    const Window root = RootWindow(display, screen);
    Colormap colormap = XCreateColormap(display, root, visual, AllocNone);
    XSetWindowAttributes attributes{};
    attributes.colormap = colormap;
    attributes.background_pixel = 0;
    attributes.border_pixel = 0;
    Window window = XCreateWindow(display, root, 0, 0, width, height, 0, depth,
                                  InputOutput, visual, CWColormap | CWBackPixel | CWBorderPixel,
                                  &attributes);
    Atom overlay = XInternAtom(display, "GAMESCOPE_EXTERNAL_OVERLAY", False);
    unsigned long enabled = 1;
    XChangeProperty(display, window, overlay, XA_CARDINAL, 32, PropModeReplace,
                    reinterpret_cast<unsigned char *>(&enabled), 1);
    XWMHints hints{};
    hints.flags = InputHint;
    hints.input = False;
    XSetWMHints(display, window, &hints);
    XShapeCombineMask(display, window, ShapeInput, 0, 0, None, ShapeSet);
    Atom state = XInternAtom(display, "_NET_WM_STATE", False);
    Atom fullscreen = XInternAtom(display, "_NET_WM_STATE_FULLSCREEN", False);
    XChangeProperty(display, window, state, XA_ATOM, 32, PropModeReplace,
                    reinterpret_cast<unsigned char *>(&fullscreen), 1);
    XMapRaised(display, window);
    XFlush(display);

    XImage *image = XCreateImage(display, visual, depth, ZPixmap,
                                 0, nullptr, width, height, 32, 0);
    if (!image || image->bits_per_pixel != 32 || image->byte_order != LSBFirst) {
        std::fprintf(stderr, "Unsupported X11 image depth.\n");
        if (image) XDestroyImage(image);
        XDestroyWindow(display, window);
        XFreeColormap(display, colormap);
        XCloseDisplay(display);
        return 4;
    }
    image->data = static_cast<char *>(std::calloc(height, image->bytes_per_line));
    if (!image->data) {
        std::fprintf(stderr, "Could not allocate display image.\n");
        XDestroyImage(image);
        XDestroyWindow(display, window);
        XFreeColormap(display, colormap);
        XCloseDisplay(display);
        return 5;
    }
    GC gc = XCreateGC(display, window, 0, nullptr);
    MediaBridge bridge;
    if (!ipc_path.empty() && !bridge.start(ipc_path)) {
        XFreeGC(display, gc);
        XDestroyImage(image);
        XDestroyWindow(display, window);
        XFreeColormap(display, colormap);
        XCloseDisplay(display);
        return 9;
    }
    Capture capture;
    if (mode != "pattern" && mode != "direct-pattern" &&
        !start_capture(capture, mode == "synthetic" || mode == "direct-test", direct,
                                              width, height, game.x, game.y, game.width,
                                              game.height, ipc_path.empty() ? nullptr : &bridge)) {
        std::fprintf(stderr, "Could not start capture process.\n");
        bridge.stop();
        XFreeGC(display, gc);
        XDestroyImage(image);
        XDestroyWindow(display, window);
        XFreeColormap(display, colormap);
        XCloseDisplay(display);
        return 6;
    }
    std::fprintf(stderr, "Stream Share started: %s, layout=%s (%dx%d).\n",
                 mode.c_str(), layout.c_str(), width, height);
    std::fflush(stderr);
    int result = 0;
    unsigned long displayed_local_frames = 0;
    unsigned long last_displayed_capture = 0;
    std::vector<unsigned char> frame;
    const auto started = std::chrono::steady_clock::now();
    const auto limit = mode == "pattern" || mode == "direct-pattern" ? std::chrono::seconds(45) :
                       (ipc_path.empty() ? std::chrono::seconds(90) : std::chrono::hours(4));
    while (running) {
        if (std::chrono::steady_clock::now() - started >= limit) {
            std::fprintf(stderr, "Split view time limit reached; closing overlay.\n");
            break;
        }
        if (mode != "pattern" && !direct) {
            std::unique_lock<std::mutex> lock(capture.mutex);
            capture.updated.wait_for(lock, std::chrono::milliseconds(100), [&] {
                return capture.frames != last_displayed_capture || capture.done || !running;
            });
            if (capture.frames != last_displayed_capture) {
                frame = capture.latest;
                last_displayed_capture = capture.frames;
            }
        }
        const std::vector<unsigned char> remote = bridge.remote_frame();
        render(image, frame, remote, mode == "pattern", direct, game, friend_view);
        XPutImage(display, window, gc, image, 0, 0, 0, 0, width, height);
        if (!frame.empty() && ++displayed_local_frames == 10) {
            std::fprintf(stderr, "Displayed 10 local game frames.\n");
            std::fflush(stderr);
        }
        XFlush(display);
        if (running && mode != "pattern" && capture.done) {
            std::fprintf(stderr, "Game capture stopped. Check GStreamer errors above.\n");
            result = 7;
            break;
        }
        if (mode == "pattern" || direct)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    stop_capture(capture);
    bridge.stop();
    XFreeGC(display, gc);
    XDestroyImage(image);
    XDestroyWindow(display, window);
    XFreeColormap(display, colormap);
    XCloseDisplay(display);
    return result;
}
