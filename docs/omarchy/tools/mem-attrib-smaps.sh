#!/system/bin/sh
# Runs ON the device as the app uid (adb shell run-as <pkg> sh < this file).
# One row per mapping with pss>0 for the app process, Hyprland, Quickshell, cage and Xwayland:
#   <label> <pid> pss=<kB> rss=<kB> pd=<kB> swap=<kB> perm=<rwxp> size=<kB> <name or ->
# Label comes from /proc/<pid>/comm, so proot tracees are told apart directly.
exec 2>/dev/null
dump() { # $1 pid, $2 label
  awk -v L="$2" -v P="$1" '
    function flush() { if (have && pss > 0) printf "%s %s pss=%d rss=%d pd=%d swap=%d perm=%s size=%d %s\n", L, P, pss, rss, pd, sw, perm, size, (name == "" ? "-" : name); have = 0 }
    /^[0-9a-f]+-[0-9a-f]+ / {
      flush(); have = 1; perm = $2; name = ""
      for (i = 6; i <= NF; i++) name = (name == "" ? $i : name " " $i)
      split($1, a, "-"); pss = 0; rss = 0; pd = 0; sw = 0; size = 0; next }
    /^Size:/ { size = $2 }
    /^Rss:/ { rss = $2 }
    /^Pss:/ { pss = $2 }
    /^Private_Dirty:/ { pd = $2 }
    /^SwapPss:/ { sw = $2 }
    END { flush() }
  ' /proc/$1/smaps
}
app=$(pidof com.phoshdroid.app)
[ -n "$app" ] && dump "$app" app
for p in /proc/[0-9]*; do
  c=""; read -r c < "$p/comm" || continue
  pid=${p#/proc/}
  case "$c" in
    Hyprland) dump "$pid" Hyprland ;;
    quickshell|qs|.quickshell-wrapp*) dump "$pid" Quickshell ;;
    cage) dump "$pid" cage ;;
    Xwayland) dump "$pid" Xwayland ;;
  esac
done
