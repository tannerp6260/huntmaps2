// The existing reverse directed Dijkstra, with identical heap and neighbor order.
// No fast math, reassociation, contraction, parallelism or approximate costs.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <memory>
#include <new>
#include <queue>
#include <utility>
#include <vector>

struct Search {
    int rows, cols;
    double resolution, maximum, degrees, diagonal;
    const double *dem, *slope, *tree, *shrub, *weights;
    const uint8_t *valid, *edges;
    double *dist;
    int64_t *next;
    using Entry = std::pair<double, int64_t>;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
};

extern "C" void *hm_start(int rows, int cols, double resolution, double maximum,
                          double degrees, double diagonal, const double *dem,
                          const double *slope, const double *tree, const double *shrub,
                          const uint8_t *valid, const uint8_t *edges,
                          const double *weights, int64_t end, double initial,
                          double *dist, int64_t *next) {
    try {
        auto s = std::make_unique<Search>(Search{rows, cols, resolution, maximum, degrees, diagonal,
                             dem, slope, tree, shrub, weights, valid, edges, dist, next, {}});
        std::fill(dist, dist + int64_t(rows) * cols, std::numeric_limits<double>::infinity());
        std::fill(next, next + int64_t(rows) * cols, -1);
        dist[end] = initial;
        s->queue.push({initial, end});
        return s.release();
    } catch (const std::bad_alloc &) { return nullptr; }
}

extern "C" int hm_step(void *handle, int count) {
    auto &s = *static_cast<Search *>(handle);
    constexpr int directions[8][2] = {{-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}};
    const int64_t size = int64_t(s.rows) * s.cols;
    try {
        while (!s.queue.empty() && count-- > 0) {
            auto [cost, cell] = s.queue.top(); s.queue.pop();
            if (cost != s.dist[cell]) continue;
            const int r = cell / s.cols, c = cell % s.cols;
            for (const auto &d : directions) {
                const int nr = r + d[0], nc = c + d[1];
                if (nr < 0 || nr >= s.rows || nc < 0 || nc >= s.cols) continue;
                const int64_t n = int64_t(nr) * s.cols + nc;
                if (!s.valid[n]) continue;
                if (d[0] && d[1] && (!s.valid[int64_t(nr)*s.cols+c] || !s.valid[int64_t(r)*s.cols+nc])) continue;
                int dr = -d[0], dc = -d[1];
                int64_t source = n;
                if (dr < 0 || (dr == 0 && dc < 0)) { source = cell; dr = -dr; dc = -dc; }
                const int direction = dr == 0 ? 0 : dc == -1 ? 1 : dc == 0 ? 2 : 3;
                if (!s.edges[direction * size + source]) continue;
                const double length = s.resolution * (dr && dc ? s.diagonal : 1.0);
                const double dz = s.dem[cell] - s.dem[n];
                const double slope = std::max(std::max(s.slope[cell], s.slope[n]),
                                               std::atan2(std::abs(dz), length) * s.degrees);
                if (slope > s.maximum) continue;
                const double edge_cost = length * (1.0 + s.weights[0] * std::pow(slope / 15.0, 2.0)
                    + s.weights[1] * (s.tree[n] + s.tree[cell]) / 2.0
                    + s.weights[2] * (s.shrub[n] + s.shrub[cell]) / 2.0)
                    + s.weights[3] * 10.0 * std::max(0.0, dz);
                const double value = cost + edge_cost;
                if (value < s.dist[n]) {
                    s.dist[n] = value; s.next[n] = cell;
                    s.queue.push({value, n});
                }
            }
        }
        return s.queue.empty() ? 0 : 1;
    } catch (const std::bad_alloc &) { return -1; }
}

extern "C" void hm_stop(void *handle) { delete static_cast<Search *>(handle); }
