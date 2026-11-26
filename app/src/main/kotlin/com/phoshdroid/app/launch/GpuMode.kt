package com.phoshdroid.app.launch

import java.io.File

/**
 * Which GPU path the guest session uses (contract section 9).
 *
 * `KGSL` is the patched Mesa talking to an Adreno GPU through `/dev/kgsl-3d0`. `SOFTWARE` is the
 * same Mesa's llvmpipe rasteriser on the CPU: it needs no GPU node, so it boots on a Mali, Xclipse,
 * PowerVR or Tensor phone, slowly.
 */
enum class GpuMode(
    /** The value of `OMDROID_GPU` in the guest environment. */
    val value: String,
) {
    KGSL("kgsl"),
    SOFTWARE("software"),
}

/**
 * The host's GPU decision: a pure rule plus the one probe that feeds it.
 *
 * The stored preference is `auto` (the default), `kgsl` or `software`. `auto` follows the device:
 * KGSL when the Adreno node is usable, software otherwise. The two explicit choices are honoured
 * even when the probe disagrees, so a user can force KGSL on a device whose node the probe
 * misjudges, or force software on an Adreno phone to compare.
 */
object GpuModeRule {
    const val AUTO = "auto"
    const val KGSL = "kgsl"
    const val SOFTWARE = "software"

    /** The Adreno node the patched Mesa opens. */
    const val KGSL_DEVICE = "/dev/kgsl-3d0"

    /** `OMDROID_GPU_SOURCE` when the mode came from `auto`: the guest may fall back (contract section 9). */
    const val SOURCE_AUTO = "auto"

    /** `OMDROID_GPU_SOURCE` when the user chose the mode: the guest never overrides it. */
    const val SOURCE_SETTING = "setting"

    /** An unknown or missing stored value means `auto`. */
    fun normalise(preference: String?): String =
        when (preference?.trim()) {
            KGSL -> KGSL
            SOFTWARE -> SOFTWARE
            else -> AUTO
        }

    fun resolve(
        preference: String?,
        kgslUsable: Boolean,
    ): GpuMode =
        when (normalise(preference)) {
            KGSL -> GpuMode.KGSL
            SOFTWARE -> GpuMode.SOFTWARE
            else -> if (kgslUsable) GpuMode.KGSL else GpuMode.SOFTWARE
        }

    /** `auto` or `setting`: who made the choice, so the guest knows whether it may change it. */
    fun source(preference: String?): String =
        if (normalise(preference) == AUTO) SOURCE_AUTO else SOURCE_SETTING

    /**
     * Whether the app can use the Adreno node: it exists and this process may read and write it.
     * `canRead`/`canWrite` go through `access(2)`, which the kernel also checks against SELinux,
     * so a device that hides the node from apps reads as unusable here.
     */
    fun isKgslUsable(device: File = File(KGSL_DEVICE)): Boolean =
        try {
            device.exists() && device.canRead() && device.canWrite()
        } catch (_: SecurityException) {
            false
        }
}
