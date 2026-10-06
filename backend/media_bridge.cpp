#include "media_bridge.h"

#define STBI_ONLY_JPEG
#define STBI_NO_STDIO
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STBI_WRITE_NO_STDIO
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

#include <arpa/inet.h>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

namespace {
constexpr int kWidth = 640;
constexpr int kHeight = 400;
constexpr size_t kFrameBytes = kWidth * kHeight * 4;
constexpr uint32_t kMaxJpegBytes = 512 * 1024 - 1;

void collect_jpeg(void *context, void *data, int size) {
    auto *bytes = static_cast<std::vector<unsigned char> *>(context);
    auto *first = static_cast<unsigned char *>(data);
    bytes->insert(bytes->end(), first, first + size);
}
} // namespace

MediaBridge::~MediaBridge() { stop(); }

bool MediaBridge::start(const std::string &path) {
    if (path.size() >= sizeof(sockaddr_un::sun_path)) {
        std::fprintf(stderr, "Media socket path is too long.\n");
        return false;
    }
    fd_ = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd_ < 0) return false;
    sockaddr_un address{};
    address.sun_family = AF_UNIX;
    std::memcpy(address.sun_path, path.c_str(), path.size() + 1);
    if (connect(fd_, reinterpret_cast<sockaddr *>(&address), sizeof(address)) != 0) {
        std::fprintf(stderr, "Cannot connect to local media socket: %s\n", std::strerror(errno));
        close(fd_);
        fd_ = -1;
        return false;
    }
    active_ = true;
    encoder_ = std::thread(&MediaBridge::encode_loop, this);
    receiver_ = std::thread(&MediaBridge::receive_loop, this);
    std::fprintf(stderr, "Local media bridge connected.\n");
    return true;
}

void MediaBridge::submit(const std::vector<unsigned char> &frame) {
    if (!active_ || frame.size() != kFrameBytes) return;
    {
        std::lock_guard<std::mutex> lock(outgoing_mutex_);
        pending_ = frame;
    }
    outgoing_ready_.notify_one();
}

std::vector<unsigned char> MediaBridge::remote_frame() {
    std::lock_guard<std::mutex> lock(remote_mutex_);
    return remote_;
}

bool MediaBridge::read_exact(void *buffer, size_t count) {
    auto *bytes = static_cast<unsigned char *>(buffer);
    size_t offset = 0;
    while (active_ && offset < count) {
        ssize_t n = read(fd_, bytes + offset, count - offset);
        if (n == 0) return false;
        if (n < 0) {
            if (errno == EINTR) continue;
            return false;
        }
        offset += static_cast<size_t>(n);
    }
    return offset == count;
}

bool MediaBridge::write_exact(const void *buffer, size_t count) {
    const auto *bytes = static_cast<const unsigned char *>(buffer);
    size_t offset = 0;
    while (active_ && offset < count) {
        ssize_t n = write(fd_, bytes + offset, count - offset);
        if (n < 0) {
            if (errno == EINTR) continue;
            return false;
        }
        offset += static_cast<size_t>(n);
    }
    return offset == count;
}

bool MediaBridge::send_packet(const std::vector<unsigned char> &jpeg) {
    if (jpeg.empty() || jpeg.size() > kMaxJpegBytes) return false;
    unsigned char header[5] = {'V', 0, 0, 0, 0};
    uint32_t length = htonl(static_cast<uint32_t>(jpeg.size()));
    std::memcpy(header + 1, &length, 4);
    return write_exact(header, sizeof(header)) && write_exact(jpeg.data(), jpeg.size());
}

void MediaBridge::encode_loop() {
    std::vector<unsigned char> rgb(kWidth * kHeight * 3);
    unsigned long frames = 0;
    while (active_) {
        std::vector<unsigned char> source;
        {
            std::unique_lock<std::mutex> lock(outgoing_mutex_);
            outgoing_ready_.wait(lock, [this] { return !active_ || !pending_.empty(); });
            if (!active_) break;
            source.swap(pending_);
        }
        for (size_t i = 0, j = 0; i < source.size(); i += 4, j += 3) {
            rgb[j] = source[i + 2];
            rgb[j + 1] = source[i + 1];
            rgb[j + 2] = source[i];
        }
        std::vector<unsigned char> jpeg;
        if (!stbi_write_jpg_to_func(collect_jpeg, &jpeg, kWidth, kHeight, 3, rgb.data(), 55)) {
            std::fprintf(stderr, "JPEG encode failed.\n");
            break;
        }
        if (!send_packet(jpeg)) {
            std::fprintf(stderr, "Local video relay disconnected.\n");
            break;
        }
        if (++frames == 1 || frames % 75 == 0)
            std::fprintf(stderr, "Sent %lu JPEG frames.\n", frames);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    if (active_.exchange(false)) shutdown(fd_, SHUT_RDWR);
    outgoing_ready_.notify_all();
}

void MediaBridge::receive_loop() {
    unsigned long frames = 0;
    while (active_) {
        unsigned char header[5];
        if (!read_exact(header, sizeof(header))) break;
        uint32_t network_length;
        std::memcpy(&network_length, header + 1, 4);
        const uint32_t length = ntohl(network_length);
        if (header[0] != 'V' || length == 0 || length > kMaxJpegBytes) break;
        std::vector<unsigned char> jpeg(length);
        if (!read_exact(jpeg.data(), jpeg.size())) break;
        int width = 0, height = 0, channels = 0;
        if (!stbi_info_from_memory(jpeg.data(), static_cast<int>(jpeg.size()),
                                   &width, &height, &channels) ||
            width != kWidth || height != kHeight) continue;
        unsigned char *rgb = stbi_load_from_memory(jpeg.data(), static_cast<int>(jpeg.size()),
                                                   &width, &height, &channels, 3);
        if (!rgb) continue;
        std::vector<unsigned char> frame(kFrameBytes);
        for (size_t i = 0, j = 0; j < frame.size(); i += 3, j += 4) {
            frame[j] = rgb[i + 2];
            frame[j + 1] = rgb[i + 1];
            frame[j + 2] = rgb[i];
        }
        stbi_image_free(rgb);
        {
            std::lock_guard<std::mutex> lock(remote_mutex_);
            remote_.swap(frame);
        }
        if (++frames == 1 || frames % 75 == 0)
            std::fprintf(stderr, "Received %lu friend frames.\n", frames);
    }
    if (active_.exchange(false)) shutdown(fd_, SHUT_RDWR);
    outgoing_ready_.notify_all();
}

void MediaBridge::stop() {
    active_ = false;
    outgoing_ready_.notify_all();
    if (fd_ >= 0) shutdown(fd_, SHUT_RDWR);
    if (encoder_.joinable()) encoder_.join();
    if (receiver_.joinable()) receiver_.join();
    if (fd_ >= 0) close(fd_);
    fd_ = -1;
}
