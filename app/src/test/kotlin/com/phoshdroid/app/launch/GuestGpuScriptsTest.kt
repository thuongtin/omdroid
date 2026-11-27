package com.phoshdroid.app.launch

import com.phoshdroid.app.proot.ProotCommandBuilder
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.io.File

/**
 * Runs the guest's GPU logic in a real bash: the GPU block of `start.sh` and the fallback in
 * `session-child.sh`. The host's [ProotCommandBuilder] and the guest scripts state the same two
 * environment blocks; these tests are what keeps them equal.
 *
 * Nothing here touches the machine running the tests: the scripts get a clean environment, a
 * temporary runtime dir, a fake Hyprland and a fake `pkill` that only records its arguments.
 */
class GuestGpuScriptsTest {
    @TempDir
    lateinit var dir: File

    private val overlay: File =
        generateSequence(File("").absoluteFile) { it.parentFile }
            .map { File(it, "rootfs/overlay/etc/phoshdroid") }
            .first { File(it, "start.sh").isFile }

    private val builder = ProotCommandBuilder(nativeLibDir = "/native", prefixDir = "/prefix", distroName = "omarchy")

    private fun hostEnvironment(
        gpu: GpuMode,
        source: String = GpuModeRule.SOURCE_AUTO,
    ) = builder.buildEnvironment(
        width = 3200,
        height = 1971,
        scale = 2,
        refreshMhz = 120_000,
        gpu = gpu,
        gpuSource = source,
    )

    private fun bash(
        script: File,
        env: Map<String, String>,
    ): Pair<Int, String> {
        val pb = ProcessBuilder("bash", script.path).redirectErrorStream(true)
        pb.environment().clear()
        pb.environment().putAll(env)
        val process = pb.start()
        val output = process.inputStream.bufferedReader().readText()
        return process.waitFor() to output
    }

    // ---- start.sh: the GPU block -------------------------------------------------------------

    private fun gpuBlock(): String {
        val text = File(overlay, "start.sh").readText()
        val from = text.indexOf("# GPU path (launch-contract section 9)")
        val to = text.indexOf("# Fake root:")
        assertTrue(from in 0 until to, "start.sh must keep its GPU block between the GPU path and Fake root comments")
        return text.substring(from, to)
    }

    private fun runGpuBlock(env: Map<String, String>): Pair<Map<String, String>, String> {
        val script =
            File(dir, "gpu-block-${System.nanoTime()}.sh").apply {
                writeText(
                    "export XDG_RUNTIME_DIR='${dir.path}'\nexport OMARCHY_REFRESH_MHZ=120000\n" +
                        gpuBlock() + "\nenv\n",
                )
            }
        val (code, out) = bash(script, mapOf("PATH" to "/usr/bin:/bin") + env)
        assertEquals(0, code, out)
        val vars =
            out
                .lines()
                .filter { Regex("^[A-Z_0-9]+=").containsMatchIn(it) }
                .associate { it.substringBefore('=') to it.substringAfter('=') }
        return vars to out
    }

    // Variables the block exports (or removes) in both modes; each must equal what the host passes.
    private val compared =
        listOf(
            "OMARCHY_GPU_MODE",
            "MESA_LOADER_DRIVER_OVERRIDE",
            "VK_ICD_FILENAMES",
            "FD_KGSL_ENABLE_DMABUF",
            "HYPRLAND_ANDROID_DMABUF",
            "LIBGL_ALWAYS_SOFTWARE",
            "GALLIUM_DRIVER",
            "LIBGL_DRIVERS_PATH",
            "AQ_NO_KMS_REQUIREMENT",
            "AQ_NO_MODIFIERS",
            "AQ_WAYLAND_REFRESH_MHZ",
            "HYPRLAND_SHM_DAMAGE",
            "HYPRLAND_EGL_NO_MODIFIERS",
            "HYPRLAND_EGL_SURFACELESS",
            "HYPRLAND_NO_SD_NOTIFY",
            "HYPRLAND_NO_SD_VARS",
            "HYPRLAND_NO_RT",
            "QT_QPA_PLATFORM",
            "GDK_BACKEND",
            "SDL_VIDEODRIVER",
            "XWAYLAND_NO_GLAMOR",
            "NO_AT_BRIDGE",
            "QT_ACCESSIBILITY",
            "GTK_A11Y",
        )

    @Test
    fun `the guest KGSL block exports what the host passes`() {
        val host = hostEnvironment(GpuMode.KGSL)

        val (guest, _) = runGpuBlock(mapOf("OMDROID_GPU" to "kgsl", "OMDROID_GPU_SOURCE" to "auto"))

        for (key in compared) assertEquals(host[key], guest[key], key)
        assertEquals("kgsl", guest["OMDROID_GPU"])
    }

    @Test
    fun `the guest software block exports what the host passes and drops what the host drops`() {
        val host = hostEnvironment(GpuMode.SOFTWARE)
        // A stale shell that was KGSL before: the block has to remove those variables.
        val stale =
            mapOf(
                "MESA_LOADER_DRIVER_OVERRIDE" to "kgsl",
                "VK_ICD_FILENAMES" to "/opt/omarchy-android/mesa/freedreno_icd.json",
                "FD_KGSL_ENABLE_DMABUF" to "1",
                "HYPRLAND_ANDROID_DMABUF" to "1",
            )

        val (guest, _) = runGpuBlock(stale + mapOf("OMDROID_GPU" to "software", "OMDROID_GPU_SOURCE" to "auto"))

        for (key in compared) assertEquals(host[key], guest[key], key)
        assertNull(guest["VK_ICD_FILENAMES"])
        assertNull(guest["FD_KGSL_ENABLE_DMABUF"])
        assertNull(guest["HYPRLAND_ANDROID_DMABUF"])
    }

    @Test
    fun `the KGSL block removes a leftover software override`() {
        val (guest, _) =
            runGpuBlock(
                mapOf(
                    "OMDROID_GPU" to "kgsl",
                    "OMDROID_GPU_SOURCE" to "setting",
                    "LIBGL_ALWAYS_SOFTWARE" to "1",
                    "GALLIUM_DRIVER" to "llvmpipe",
                ),
            )

        assertNull(guest["LIBGL_ALWAYS_SOFTWARE"])
        assertNull(guest["GALLIUM_DRIVER"])
        assertEquals("kgsl", guest["MESA_LOADER_DRIVER_OVERRIDE"])
    }

    @Test
    fun `a manual launch with no host probes the node and counts as auto`() {
        // The machine running the tests has no Adreno node.
        val (guest, out) = runGpuBlock(emptyMap())

        assertEquals("software", guest["OMDROID_GPU"])
        assertEquals("auto", guest["OMDROID_GPU_SOURCE"])
        assertTrue(out.contains("gpu: mode=software source=auto from=probe"), out)
    }

    @Test
    fun `an unknown host value is replaced by the probe`() {
        val (guest, out) = runGpuBlock(mapOf("OMDROID_GPU" to "virgl"))

        assertEquals("software", guest["OMDROID_GPU"])
        assertTrue(out.contains("from=probe"), out)
    }

    @Test
    fun `a fallback marker turns an auto KGSL start into software`() {
        File(dir, "omdroid-gpu-fallback").writeText("")

        val (guest, out) = runGpuBlock(mapOf("OMDROID_GPU" to "kgsl", "OMDROID_GPU_SOURCE" to "auto"))

        assertEquals("software", guest["OMDROID_GPU"])
        assertEquals("swrast", guest["MESA_LOADER_DRIVER_OVERRIDE"])
        assertTrue(out.contains("gpu: mode=software source=auto from=marker"), out)
    }

    @Test
    fun `a fallback marker never overrides a mode the user chose`() {
        File(dir, "omdroid-gpu-fallback").writeText("")

        val (guest, out) = runGpuBlock(mapOf("OMDROID_GPU" to "kgsl", "OMDROID_GPU_SOURCE" to "setting"))

        assertEquals("kgsl", guest["OMDROID_GPU"])
        assertTrue(out.contains("gpu: mode=kgsl source=setting from=host"), out)
    }

    // ---- session-child.sh: the one-shot fallback ---------------------------------------------

    private val fakeLog get() = File(dir, "hyprland-starts.log")
    private val pkillLog get() = File(dir, "pkill.log")

    /** A copy of session-child.sh that runs a fake Hyprland and a fake pkill instead of the guest's. */
    private fun sessionChild(): File {
        val fakeHyprland =
            File(dir, "fake-hyprland").apply {
                writeText(
                    "#!/bin/bash\n" +
                        "echo \"hypr gpu=\$OMDROID_GPU mode=\$OMARCHY_GPU_MODE driver=\$MESA_LOADER_DRIVER_OVERRIDE " +
                        "vk=\${VK_ICD_FILENAMES:-none}\" >> '${fakeLog.path}'\n" +
                        "if [ \"\$OMDROID_GPU\" = software ]; then exit \"\${FAKE_SOFT_RC:-0}\"; fi\n" +
                        "exit \"\${FAKE_KGSL_RC:-3}\"\n",
                )
                setExecutable(true)
            }
        val bin = File(dir, "bin").apply { mkdirs() }
        File(bin, "pkill").apply {
            writeText("#!/bin/bash\necho \"\$@\" >> '${pkillLog.path}'\n")
            setExecutable(true)
        }
        val text =
            File(overlay, "session-child.sh")
                .readText()
                .replace("/opt/omarchy-android/hyprland/bin/Hyprland", fakeHyprland.path)
                .replace("python3 /etc/phoshdroid/fit-x11.py", "true")
        return File(dir, "session-child.sh").apply { writeText(text) }
    }

    private fun runSessionChild(env: Map<String, String>): Pair<Int, String> {
        fakeLog.delete()
        pkillLog.delete()
        File(dir, "omdroid-gpu-fallback").delete()
        File(dir, "hypr/stale-instance").mkdirs()
        val base = mapOf("PATH" to "${File(dir, "bin").path}:/usr/bin:/bin", "XDG_RUNTIME_DIR" to dir.path)
        return bash(sessionChild(), base + env)
    }

    private fun starts(): List<String> = if (fakeLog.exists()) fakeLog.readLines() else emptyList()

    private val autoKgsl =
        mapOf(
            "OMDROID_GPU" to "kgsl",
            "OMDROID_GPU_SOURCE" to "auto",
            "OMARCHY_GPU_MODE" to "kgsl",
            "MESA_LOADER_DRIVER_OVERRIDE" to "kgsl",
            "VK_ICD_FILENAMES" to "/opt/omarchy-android/mesa/freedreno_icd.json",
        )

    @Test
    fun `an auto KGSL start that dies at once is retried once in software mode`() {
        val (code, out) = runSessionChild(autoKgsl)

        assertEquals(0, code, out)
        assertEquals(
            listOf(
                "hypr gpu=kgsl mode=kgsl driver=kgsl vk=/opt/omarchy-android/mesa/freedreno_icd.json",
                "hypr gpu=software mode=software driver=swrast vk=none",
            ),
            starts(),
        )
        assertTrue(File(dir, "omdroid-gpu-fallback").exists(), "the marker for a host retry")
        assertFalse(File(dir, "hypr/stale-instance").exists(), "the failed instance dir is removed")
        assertTrue(pkillLog.readText().contains("quickshell"), "the failed start's shell is stopped")
        assertTrue(out.contains("starting it once more in software mode"), out)
    }

    @Test
    fun `a KGSL start that works is not retried`() {
        val (code, out) = runSessionChild(autoKgsl + mapOf("FAKE_KGSL_RC" to "0"))

        assertEquals(0, code, out)
        assertEquals(1, starts().size)
        assertFalse(File(dir, "omdroid-gpu-fallback").exists())
    }

    @Test
    fun `a software start that also dies reports its own exit code`() {
        val (code, out) = runSessionChild(autoKgsl + mapOf("FAKE_SOFT_RC" to "5"))

        assertEquals(5, code, out)
        assertEquals(2, starts().size)
    }

    @Test
    fun `a mode the user chose is never retried`() {
        val (code, out) = runSessionChild(autoKgsl + mapOf("OMDROID_GPU_SOURCE" to "setting"))

        assertEquals(3, code, out)
        assertEquals(1, starts().size)
        assertFalse(File(dir, "omdroid-gpu-fallback").exists())
    }

    @Test
    fun `the fallback can be switched off`() {
        val (code, out) = runSessionChild(autoKgsl + mapOf("OMDROID_GPU_FALLBACK" to "0"))

        assertEquals(3, code, out)
        assertEquals(1, starts().size)
    }

    @Test
    fun `a start that runs past the window is not a driver failure`() {
        val (code, out) = runSessionChild(autoKgsl + mapOf("OMDROID_GPU_FALLBACK_WINDOW" to "0"))

        assertEquals(3, code, out)
        assertEquals(1, starts().size)
    }

    @Test
    fun `a software start execs Hyprland and keeps its exit code`() {
        val (code, out) =
            runSessionChild(
                mapOf(
                    "OMDROID_GPU" to "software",
                    "OMDROID_GPU_SOURCE" to "auto",
                    "OMARCHY_GPU_MODE" to "software",
                    "MESA_LOADER_DRIVER_OVERRIDE" to "swrast",
                    "FAKE_SOFT_RC" to "4",
                ),
            )

        assertEquals(4, code, out)
        assertEquals(1, starts().size)
    }
}
