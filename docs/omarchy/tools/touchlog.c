/* touchlog [seconds] [layer]  -- a full-output, input-catching layer surface that prints every
 * wl_touch and wl_pointer event it receives, with surface-local (= output logical) coordinates.
 *
 * Used by the R5 touch device round to prove where a finger lands: the surface is anchored to
 * all four edges with exclusive zone -1, so it covers the whole output at 0,0 and its local
 * coordinates are Hyprland's logical coordinates. Exits after [seconds] (default 30).
 * layer: 3 = overlay (default, above everything), 0 = background (below everything).
 *
 * Build (the guest image's toolchain, in the aquamarine builder container), then run it inside the
 * live session so it gets Hyprland's WAYLAND_DISPLAY:
 *   curl -sfLO https://gitlab.freedesktop.org/wlroots/wlr-protocols/-/raw/master/unstable/wlr-layer-shell-unstable-v1.xml
 *   docker cp touchlog.c wlr-layer-shell-unstable-v1.xml omdroid-aquamarine-builder:/tmp/tl/   (one file per cp)
 *   docker exec -w /tmp/tl omdroid-aquamarine-builder sh -c '
 *     wayland-scanner client-header wlr-layer-shell-unstable-v1.xml wlr-layer-shell-unstable-v1-client-protocol.h
 *     wayland-scanner private-code wlr-layer-shell-unstable-v1.xml wlr-layer-shell-unstable-v1-protocol.c
 *     wayland-scanner private-code /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml xdg-shell-protocol.c
 *     clang -O1 -o touchlog touchlog.c wlr-layer-shell-unstable-v1-protocol.c xdg-shell-protocol.c -lwayland-client'
 *   adb push touchlog /data/local/tmp/ && adb shell run-as com.phoshdroid.app cp /data/local/tmp/touchlog files/usr/tmp/
 *   ./hc.sh '/dispatch hl.dsp.exec_cmd("/tmp/touchlog 40 > /tmp/touchlog.out 2>&1")'
 *   ... touch the screen ...;  adb shell run-as com.phoshdroid.app cat files/usr/tmp/touchlog.out
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include "wlr-layer-shell-unstable-v1-client-protocol.h"

static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_seat *seat;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct wl_surface *surface;
static struct zwlr_layer_surface_v1 *layer_surface;
static struct wl_touch *touch;
static struct wl_pointer *pointer;
static int running = 1;
static double t0;

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

#define LOG(...) do { printf("%8.3f ", now() - t0); printf(__VA_ARGS__); printf("\n"); fflush(stdout); } while (0)

static struct wl_buffer *make_buffer(int w, int h) {
    int stride = w * 4, size = stride * h;
    int fd = memfd_create("touchlog", MFD_CLOEXEC);
    if (fd < 0 || ftruncate(fd, size) < 0) { perror("memfd"); exit(1); }
    uint32_t *px = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (px == MAP_FAILED) { perror("mmap"); exit(1); }
    for (int i = 0; i < w * h; i++) px[i] = 0x30ff0080; /* faint magenta tint, premultiplied-ish */
    /* a 1-px frame so the covered area is visible in a screenshot */
    for (int x = 0; x < w; x++) { px[x] = 0xffff00ff; px[(h - 1) * w + x] = 0xffff00ff; }
    for (int y = 0; y < h; y++) { px[y * w] = 0xffff00ff; px[y * w + w - 1] = 0xffff00ff; }
    munmap(px, size);
    struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, size);
    struct wl_buffer *b = wl_shm_pool_create_buffer(pool, 0, w, h, stride, WL_SHM_FORMAT_ARGB8888);
    wl_shm_pool_destroy(pool);
    close(fd);
    return b;
}

static void ls_configure(void *d, struct zwlr_layer_surface_v1 *ls, uint32_t serial, uint32_t w, uint32_t h) {
    LOG("configure %ux%u", w, h);
    zwlr_layer_surface_v1_ack_configure(ls, serial);
    struct wl_buffer *b = make_buffer(w ? w : 1, h ? h : 1);
    wl_surface_attach(surface, b, 0, 0);
    wl_surface_damage(surface, 0, 0, w, h);
    wl_surface_commit(surface);
}
static void ls_closed(void *d, struct zwlr_layer_surface_v1 *ls) { LOG("closed"); running = 0; }
static const struct zwlr_layer_surface_v1_listener ls_listener = { ls_configure, ls_closed };

static void t_down(void *d, struct wl_touch *t, uint32_t serial, uint32_t time, struct wl_surface *s, int32_t id, wl_fixed_t x, wl_fixed_t y) {
    LOG("touch down id=%d x=%.2f y=%.2f t=%u own=%d", id, wl_fixed_to_double(x), wl_fixed_to_double(y), time, s == surface);
}
static void t_up(void *d, struct wl_touch *t, uint32_t serial, uint32_t time, int32_t id) {
    LOG("touch up id=%d t=%u", id, time);
}
static void t_motion(void *d, struct wl_touch *t, uint32_t time, int32_t id, wl_fixed_t x, wl_fixed_t y) {
    LOG("touch motion id=%d x=%.2f y=%.2f t=%u", id, wl_fixed_to_double(x), wl_fixed_to_double(y), time);
}
static void t_frame(void *d, struct wl_touch *t) { LOG("touch frame"); }
static void t_cancel(void *d, struct wl_touch *t) { LOG("touch cancel"); }
static void t_shape(void *d, struct wl_touch *t, int32_t id, wl_fixed_t maj, wl_fixed_t min) {}
static void t_orient(void *d, struct wl_touch *t, int32_t id, wl_fixed_t o) {}
static const struct wl_touch_listener touch_listener = { t_down, t_up, t_motion, t_frame, t_cancel, t_shape, t_orient };

static void p_enter(void *d, struct wl_pointer *p, uint32_t serial, struct wl_surface *s, wl_fixed_t x, wl_fixed_t y) {
    LOG("pointer enter x=%.2f y=%.2f", wl_fixed_to_double(x), wl_fixed_to_double(y));
}
static void p_leave(void *d, struct wl_pointer *p, uint32_t serial, struct wl_surface *s) { LOG("pointer leave"); }
static void p_motion(void *d, struct wl_pointer *p, uint32_t time, wl_fixed_t x, wl_fixed_t y) {
    LOG("pointer motion x=%.2f y=%.2f", wl_fixed_to_double(x), wl_fixed_to_double(y));
}
static void p_button(void *d, struct wl_pointer *p, uint32_t serial, uint32_t time, uint32_t button, uint32_t state) {
    LOG("pointer button %u %s", button, state ? "down" : "up");
}
static void p_axis(void *d, struct wl_pointer *p, uint32_t time, uint32_t axis, wl_fixed_t v) {
    LOG("pointer axis %u %.2f", axis, wl_fixed_to_double(v));
}
static void p_frame(void *d, struct wl_pointer *p) {}
static void p_axis_source(void *d, struct wl_pointer *p, uint32_t s) {}
static void p_axis_stop(void *d, struct wl_pointer *p, uint32_t time, uint32_t axis) {}
static void p_axis_discrete(void *d, struct wl_pointer *p, uint32_t axis, int32_t v) {}
static void p_axis_v120(void *d, struct wl_pointer *p, uint32_t axis, int32_t v) {}
static void p_axis_rel(void *d, struct wl_pointer *p, uint32_t axis, uint32_t dir) {}
static const struct wl_pointer_listener pointer_listener = {
    p_enter, p_leave, p_motion, p_button, p_axis, p_frame, p_axis_source, p_axis_stop, p_axis_discrete,
    p_axis_v120, p_axis_rel };

static void seat_caps(void *d, struct wl_seat *s, uint32_t caps) {
    LOG("seat caps pointer=%d keyboard=%d touch=%d", !!(caps & WL_SEAT_CAPABILITY_POINTER),
        !!(caps & WL_SEAT_CAPABILITY_KEYBOARD), !!(caps & WL_SEAT_CAPABILITY_TOUCH));
    if ((caps & WL_SEAT_CAPABILITY_TOUCH) && !touch) {
        touch = wl_seat_get_touch(s);
        wl_touch_add_listener(touch, &touch_listener, NULL);
    }
    if ((caps & WL_SEAT_CAPABILITY_POINTER) && !pointer) {
        pointer = wl_seat_get_pointer(s);
        wl_pointer_add_listener(pointer, &pointer_listener, NULL);
    }
}
static void seat_name(void *d, struct wl_seat *s, const char *n) { LOG("seat name %s", n); }
static const struct wl_seat_listener seat_listener = { seat_caps, seat_name };

static void reg_global(void *d, struct wl_registry *r, uint32_t name, const char *iface, uint32_t ver) {
    if (!strcmp(iface, wl_compositor_interface.name))
        compositor = wl_registry_bind(r, name, &wl_compositor_interface, 4);
    else if (!strcmp(iface, wl_shm_interface.name))
        shm = wl_registry_bind(r, name, &wl_shm_interface, 1);
    else if (!strcmp(iface, wl_seat_interface.name) && !seat) {
        seat = wl_registry_bind(r, name, &wl_seat_interface, ver < 8 ? ver : 8);
        wl_seat_add_listener(seat, &seat_listener, NULL);
    } else if (!strcmp(iface, zwlr_layer_shell_v1_interface.name))
        layer_shell = wl_registry_bind(r, name, &zwlr_layer_shell_v1_interface, ver < 4 ? ver : 4);
}
static void reg_remove(void *d, struct wl_registry *r, uint32_t name) {}
static const struct wl_registry_listener reg_listener = { reg_global, reg_remove };

int main(int argc, char **argv) {
    double secs = argc > 1 ? atof(argv[1]) : 30;
    int layer = argc > 2 ? atoi(argv[2]) : ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY;
    t0 = now();
    struct wl_display *dpy = wl_display_connect(NULL);
    if (!dpy) { fprintf(stderr, "touchlog: no wayland display\n"); return 1; }
    struct wl_registry *reg = wl_display_get_registry(dpy);
    wl_registry_add_listener(reg, &reg_listener, NULL);
    wl_display_roundtrip(dpy);
    if (!compositor || !shm || !layer_shell) { fprintf(stderr, "touchlog: missing globals\n"); return 1; }
    surface = wl_compositor_create_surface(compositor);
    layer_surface = zwlr_layer_shell_v1_get_layer_surface(layer_shell, surface, NULL, layer, "r5-touchlog");
    zwlr_layer_surface_v1_set_anchor(layer_surface, ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
                                     ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT | ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);
    zwlr_layer_surface_v1_set_exclusive_zone(layer_surface, -1);
    zwlr_layer_surface_v1_set_size(layer_surface, 0, 0);
    zwlr_layer_surface_v1_add_listener(layer_surface, &ls_listener, NULL);
    wl_surface_commit(surface);
    wl_display_roundtrip(dpy);
    LOG("ready layer=%d for %.0f s", layer, secs);
    struct pollfd pfd = { wl_display_get_fd(dpy), POLLIN, 0 };
    while (running && now() - t0 < secs) {
        while (wl_display_prepare_read(dpy) != 0) wl_display_dispatch_pending(dpy);
        wl_display_flush(dpy);
        if (poll(&pfd, 1, 100) > 0) wl_display_read_events(dpy);
        else wl_display_cancel_read(dpy);
        wl_display_dispatch_pending(dpy);
    }
    LOG("exit");
    zwlr_layer_surface_v1_destroy(layer_surface);
    wl_surface_destroy(surface);
    wl_display_roundtrip(dpy);
    wl_display_disconnect(dpy);
    return 0;
}
