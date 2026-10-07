#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>

#include <chrono>
#include <cstdio>
#include <cstring>
#include <thread>

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    Display *display = XOpenDisplay(nullptr);
    if (!display) return 3;
    const Atom overlay = XInternAtom(display, "GAMESCOPE_EXTERNAL_OVERLAY", False);
    const Window root = DefaultRootWindow(display);
    Window window = None;
    for (int attempt = 0; attempt < 30 && window == None; ++attempt) {
        Window parent = None;
        Window actual_root = None;
        Window *children = nullptr;
        unsigned count = 0;
        if (XQueryTree(display, root, &actual_root, &parent, &children, &count)) {
            for (unsigned index = 0; index < count; ++index) {
                Atom type = None;
                int format = 0;
                unsigned long items = 0, remaining = 0;
                unsigned char *value = nullptr;
                if (XGetWindowProperty(display, children[index], overlay, 0, 1, False,
                                       XA_CARDINAL, &type, &format, &items,
                                       &remaining, &value) == Success && items == 1 && value) {
                    window = children[index];
                }
                if (value) XFree(value);
            }
        }
        if (children) XFree(children);
        if (window == None) std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    if (window == None) {
        std::fprintf(stderr, "Overlay window not found\n");
        XCloseDisplay(display);
        return 4;
    }
    XWindowAttributes attributes{};
    if (!XGetWindowAttributes(display, window, &attributes)) return 5;
    XImage *image = XGetImage(display, window, 0, 0, attributes.width,
                             attributes.height, AllPlanes, ZPixmap);
    if (!image) return 6;
    int local_x = attributes.width / 4;
    int local_y = attributes.height / 2;
    int friend_x = attributes.width * 3 / 4;
    int friend_y = attributes.height / 2;
    if (std::strcmp(argv[1], "stack") == 0) {
        local_x = friend_x = attributes.width / 2;
        local_y = attributes.height / 4;
        friend_y = attributes.height * 3 / 4;
    }
    const unsigned local_alpha = XGetPixel(image, local_x, local_y) >> 24;
    const unsigned friend_alpha = XGetPixel(image, friend_x, friend_y) >> 24;
    const unsigned expected_friend = std::strcmp(argv[1], "full") == 0 ? 0 : 255;
    std::printf("%s: local alpha=%u, friend alpha=%u\n", argv[1],
                local_alpha, friend_alpha);
    XDestroyImage(image);
    XCloseDisplay(display);
    return local_alpha == 0 && friend_alpha == expected_friend ? 0 : 7;
}
