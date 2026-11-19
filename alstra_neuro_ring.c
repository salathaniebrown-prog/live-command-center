#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <stdatomic.h>
#include <string.h>

#define RING_CAPACITY 1024
#define NUM_CHANNELS 8

typedef struct __attribute__((aligned(64))) {
    uint64_t seq_id;
    double   timestamp_us;
    double   channels[NUM_CHANNELS];   // [0..2]: PX4 roll/pitch/yaw, [3..4]: NOAA/USGS seismic/mag, [5..7]: RF RSSI/phase/thermal
    int8_t   spikes[NUM_CHANNELS];     // Neuromorphic TCAD sparse binary spikes (-1, 0, +1)
    double   fisher_entropy;           // Information-Geometric entropy density
    uint8_t  priority_lane;            // 1 = high-surprise causal anomaly lane, 0 = suppressed heartbeat
    uint8_t  _pad[7];
} NeuroTelemetrySlot;

typedef struct {
    atomic_uint_fast64_t write_idx;
    atomic_uint_fast64_t read_idx;
    atomic_uint_fast64_t total_ingested;
    atomic_uint_fast64_t spikes_emitted;
    atomic_uint_fast64_t heartbeats_suppressed;
    double kalman_est[NUM_CHANNELS];
    double kalman_err[NUM_CHANNELS];
    double tcad_threshold[NUM_CHANNELS];
    NeuroTelemetrySlot slots[RING_CAPACITY];
} NeuroZeroCopyRing;

void neuro_ring_init(NeuroZeroCopyRing *ring) {
    if (!ring) return;
    atomic_store(&ring->write_idx, 0);
    atomic_store(&ring->read_idx, 0);
    atomic_store(&ring->total_ingested, 0);
    atomic_store(&ring->spikes_emitted, 0);
    atomic_store(&ring->heartbeats_suppressed, 0);
    for (int i = 0; i < NUM_CHANNELS; i++) {
        ring->kalman_est[i] = 0.0;
        ring->kalman_err[i] = 1.0;
        ring->tcad_threshold[i] = 0.035;
    }
}

// Spiking Kalman-Complementary Filter (SKCF) + TCAD binary spike encoder
uint64_t neuro_ring_push_raw(
    NeuroZeroCopyRing *ring,
    double timestamp_us,
    const double *raw_channels
) {
    if (!ring || !raw_channels) return 0;

    uint64_t w = atomic_fetch_add_explicit(&ring->write_idx, 1, memory_order_acq_rel);
    NeuroTelemetrySlot *slot = &ring->slots[w & (RING_CAPACITY - 1)];

    slot->seq_id = w + 1;
    slot->timestamp_us = timestamp_us;

    double fisher_sum = 0.0;
    int active_spikes = 0;

    for (int i = 0; i < NUM_CHANNELS; i++) {
        double z = raw_channels[i];
        // 1D Kalman prediction + innovation step
        double p_pred = ring->kalman_err[i] + 0.002;
        double k_gain = p_pred / (p_pred + 0.04);
        double innovation = z - ring->kalman_est[i];
        ring->kalman_est[i] = ring->kalman_est[i] + k_gain * innovation;
        ring->kalman_err[i] = (1.0 - k_gain) * p_pred;

        slot->channels[i] = ring->kalman_est[i];

        // Temporal Contrast Anomaly Detection (TCAD) sparse ternary spike
        double thresh = ring->tcad_threshold[i];
        if (innovation > thresh) {
            slot->spikes[i] = 1;
            active_spikes++;
        } else if (innovation < -thresh) {
            slot->spikes[i] = -1;
            active_spikes++;
        } else {
            slot->spikes[i] = 0;
        }

        // Fisher Information proxy: (d log p / d theta)^2 ~ (innovation / sigma)^2
        double norm_innov = innovation / (thresh + 1e-9);
        fisher_sum += norm_innov * norm_innov;
    }

    slot->fisher_entropy = fisher_sum / (double)NUM_CHANNELS;
    atomic_fetch_add_explicit(&ring->total_ingested, 1, memory_order_relaxed);

    if (active_spikes > 0 || slot->fisher_entropy > 1.25) {
        slot->priority_lane = 1;
        atomic_fetch_add_explicit(&ring->spikes_emitted, (uint64_t)active_spikes, memory_order_relaxed);
    } else {
        slot->priority_lane = 0;
        atomic_fetch_add_explicit(&ring->heartbeats_suppressed, 1, memory_order_relaxed);
    }

    return slot->seq_id;
}

int neuro_ring_pop(NeuroZeroCopyRing *ring, NeuroTelemetrySlot *out_slot) {
    if (!ring || !out_slot) return 0;
    uint64_t r = atomic_load_explicit(&ring->read_idx, memory_order_acquire);
    uint64_t w = atomic_load_explicit(&ring->write_idx, memory_order_acquire);
    if (r >= w) return 0;
    memcpy(out_slot, &ring->slots[r & (RING_CAPACITY - 1)], sizeof(NeuroTelemetrySlot));
    atomic_fetch_add_explicit(&ring->read_idx, 1, memory_order_release);
    return 1;
}

size_t neuro_ring_sizeof(void) {
    return sizeof(NeuroZeroCopyRing);
}
