package com.phoshdroid.app.proot

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class RootBrokerCommandTest {

    private fun builder() = ProotCommandBuilder(nativeLibDir = "/native", prefixDir = "/prefix", distroName = "omarchy")

    /**
     * The login command with exactly the three documented differences applied:
     * `-i 1000:1000` -> `-0`, the work directory -> `/root`, and the program ->
     * the broker. Anything else differing means the two proots are not looking
     * at the same guest.
     */
    private fun loginAsBroker(): MutableList<String> {
        val expected = builder().buildLoginCommand("/etc/phoshdroid/start.sh").toMutableList()
        val identity = expected.indexOf("-i")
        expected[identity] = "-0"
        expected.removeAt(identity + 1)
        expected[expected.indexOf("-w") + 1] = "/root"
        val shell = expected.indexOf("/bin/bash")
        expected[shell] = "/usr/bin/python3"
        expected[shell + 1] = ProotCommandBuilder.BROKER_SCRIPT
        return expected
    }

    @Test
    fun `root broker command is the login command with fake root, a root workdir and the broker program`() {
        assertEquals(loginAsBroker(), builder().buildRootBrokerCommand())
    }

    @Test
    fun `root broker runs as fake root and never as the session uid`() {
        val broker = builder().buildRootBrokerCommand()

        assertEquals(1, broker.count { it == "-0" })
        assertFalse(broker.contains("-i"))
        assertFalse(broker.contains("1000:1000"))
    }

    @Test
    fun `root broker shares the guest tmp so the sudo client can reach its socket`() {
        val broker = builder().buildRootBrokerCommand()

        assertTrue(broker.contains("/prefix/tmp:/tmp"))
        assertTrue(broker.contains(ProotCommandBuilder.BROKER_SCRIPT))
        assertTrue(broker.contains("/usr/bin/python3"))
    }

    @Test
    fun `root broker keeps the same rootfs and the same proc shadows`() {
        val broker = builder().buildRootBrokerCommand()

        assertTrue(broker.contains("/prefix/var/lib/proot-distro/installed-rootfs/omarchy"))
        assertTrue(broker.contains("/prefix/var/lib/proot-distro/installed-rootfs/omarchy/etc/phoshdroid/fake-proc/stat:/proc/stat"))
        assertTrue(broker.contains("--kill-on-exit"))
    }

    @Test
    fun `root broker follows the sdcard bind like the session`() {
        val broker = builder().buildRootBrokerCommand(bindSdcard = true)

        assertTrue(broker.contains("/sdcard:/home/omarchy/Phone"))
        assertTrue(broker.contains("/sdcard:/sdcard"))
    }

    @Test
    fun `login command still runs the session script as uid 1000`() {
        val login = builder().buildLoginCommand("/etc/phoshdroid/start.sh")

        assertTrue(login.contains("-i"))
        assertTrue(login.contains("1000:1000"))
        assertEquals(listOf("/bin/bash", "/etc/phoshdroid/start.sh"), login.takeLast(2))
    }
}
