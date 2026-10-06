#pragma once

#include <atomic>
#include <condition_variable>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

// Local Unix socket between the display helper and Decky's network backend.
// Media packets are: one ASCII kind byte, four-byte big-endian length, payload.
class MediaBridge {
public:
    MediaBridge() = default;
    ~MediaBridge();
    MediaBridge(const MediaBridge &) = delete;
    MediaBridge &operator=(const MediaBridge &) = delete;

    bool start(const std::string &path);
    void submit(const std::vector<unsigned char> &bgrx_frame);
    std::vector<unsigned char> remote_frame();
    void stop();

private:
    void encode_loop();
    void receive_loop();
    bool send_packet(const std::vector<unsigned char> &jpeg);
    bool read_exact(void *buffer, size_t count);
    bool write_exact(const void *buffer, size_t count);

    int fd_ = -1;
    std::atomic<bool> active_{false};
    std::mutex outgoing_mutex_;
    std::condition_variable outgoing_ready_;
    std::vector<unsigned char> pending_;
    std::mutex remote_mutex_;
    std::vector<unsigned char> remote_;
    std::thread encoder_;
    std::thread receiver_;
};
