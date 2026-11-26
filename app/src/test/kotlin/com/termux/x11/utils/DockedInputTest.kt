package com.termux.x11.utils

import android.view.Display
import android.view.InputDevice
import android.view.KeyEvent
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/**
 * r8: the rules behind docked keyboard and pointer capture (termux-x11 submodule,
 * `DockedInput`). The device numbers are the ones `dumpsys input` reported for Phil's
 * dock: the Corne (KEYBOARD, alphabetic, external), the Magic Trackpad (MOUSE | TOUCHPAD),
 * the tablet's keyboard cover (KEYBOARD, alphabetic, internal) and its buttons.
 */
class DockedInputTest {

    private val monitor = 14

    private fun wanted(
        alive: Boolean = true,
        started: Boolean = true,
        display: Int = monitor,
        connected: Boolean = true,
        keyguard: Boolean = false,
        dex: Boolean = false,
    ) = DockedInput.captureWanted(alive, started, display, connected, keyguard, dex)

    @Test
    fun `an X activity on a monitor captures`() {
        assertTrue(wanted())
    }

    @Test
    fun `the built-in display does not capture`() {
        assertFalse(wanted(display = Display.DEFAULT_DISPLAY))
    }

    @Test
    fun `an unknown display fails open`() {
        assertFalse(wanted(display = Display.INVALID_DISPLAY))
    }

    @Test
    fun `a destroyed or finishing activity does not capture`() {
        assertFalse(wanted(alive = false))
    }

    @Test
    fun `a stopped activity does not capture`() {
        assertFalse(wanted(started = false))
    }

    @Test
    fun `no X connection does not capture`() {
        assertFalse(wanted(connected = false))
    }

    @Test
    fun `the keyguard keeps the keyboard for the PIN`() {
        assertFalse(wanted(keyguard = true))
    }

    @Test
    fun `DeX does not capture because its pointer reaches the monitor`() {
        assertFalse(wanted(dex = true))
    }

    @Test
    fun `an external alphabetic keyboard is a desktop keyboard`() {
        assertTrue(DockedInput.isDesktopKeyboard(false, InputDevice.SOURCE_KEYBOARD, InputDevice.KEYBOARD_TYPE_ALPHABETIC))
    }

    @Test
    fun `the keyboard cover counts like any physical keyboard`() {
        // Xiaomi Keyboard: KEYBOARD | DPAD, alphabetic, internal (isExternal is not consulted)
        val cover = InputDevice.SOURCE_KEYBOARD or InputDevice.SOURCE_DPAD
        assertTrue(DockedInput.isDesktopKeyboard(false, cover, InputDevice.KEYBOARD_TYPE_ALPHABETIC))
    }

    @Test
    fun `the virtual keyboard is not a desktop keyboard`() {
        assertFalse(DockedInput.isDesktopKeyboard(true, InputDevice.SOURCE_KEYBOARD, InputDevice.KEYBOARD_TYPE_ALPHABETIC))
    }

    @Test
    fun `button-only keyboards stay with Android`() {
        // pmic_pwrkey, gpio-keys, the pen's buttons: KEYBOARD, non-alphabetic
        assertFalse(DockedInput.isDesktopKeyboard(false, InputDevice.SOURCE_KEYBOARD, InputDevice.KEYBOARD_TYPE_NON_ALPHABETIC))
    }

    @Test
    fun `a touchscreen with keys is not a desktop keyboard`() {
        val touch = InputDevice.SOURCE_KEYBOARD or InputDevice.SOURCE_TOUCHSCREEN
        assertFalse(DockedInput.isDesktopKeyboard(false, touch, InputDevice.KEYBOARD_TYPE_NON_ALPHABETIC))
    }

    @Test
    fun `mouse and trackpad are desktop pointers`() {
        assertTrue(DockedInput.isDesktopPointer(false, InputDevice.SOURCE_MOUSE))
        assertTrue(DockedInput.isDesktopPointer(false, InputDevice.SOURCE_MOUSE or InputDevice.SOURCE_TOUCHPAD))
    }

    @Test
    fun `touchscreen and stylus are not desktop pointers`() {
        assertFalse(DockedInput.isDesktopPointer(false, InputDevice.SOURCE_TOUCHSCREEN))
        assertFalse(DockedInput.isDesktopPointer(false, InputDevice.SOURCE_STYLUS or InputDevice.SOURCE_TOUCHSCREEN))
    }

    @Test
    fun `a virtual pointer is not a desktop pointer`() {
        assertFalse(DockedInput.isDesktopPointer(true, InputDevice.SOURCE_MOUSE))
    }

    @Test
    fun `the pointer sources are mouse and touchpad only`() {
        assertEquals(InputDevice.SOURCE_MOUSE or InputDevice.SOURCE_TOUCHPAD, DockedInput.POINTER_SOURCES)
        val classless = DockedInput.POINTER_SOURCES and InputDevice.SOURCE_CLASS_MASK.inv()
        assertEquals(0, classless and (InputDevice.SOURCE_TOUCHSCREEN and InputDevice.SOURCE_CLASS_MASK.inv()))
        assertEquals(0, classless and (InputDevice.SOURCE_STYLUS and InputDevice.SOURCE_CLASS_MASK.inv()))
    }

    @Test
    fun `letters, SUPER and Escape from a keyboard go to the desktop`() {
        for (key in listOf(KeyEvent.KEYCODE_A, KeyEvent.KEYCODE_META_LEFT, KeyEvent.KEYCODE_ESCAPE, KeyEvent.KEYCODE_ENTER)) {
            assertTrue(
                DockedInput.isDesktopKey(false, InputDevice.SOURCE_KEYBOARD, InputDevice.KEYBOARD_TYPE_ALPHABETIC, key),
                "key $key",
            )
        }
    }

    @Test
    fun `system keys stay with Android even from a docked keyboard`() {
        for (key in listOf(
            KeyEvent.KEYCODE_POWER, KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.KEYCODE_VOLUME_DOWN,
            KeyEvent.KEYCODE_VOLUME_MUTE, KeyEvent.KEYCODE_BRIGHTNESS_UP, KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE,
            KeyEvent.KEYCODE_SLEEP, KeyEvent.KEYCODE_WAKEUP,
        )) {
            assertFalse(
                DockedInput.isDesktopKey(false, InputDevice.SOURCE_KEYBOARD, InputDevice.KEYBOARD_TYPE_ALPHABETIC, key),
                "key $key",
            )
        }
    }

    @Test
    fun `a mouse side button goes to the desktop instead of Android Back`() {
        assertTrue(DockedInput.isDesktopKey(false, InputDevice.SOURCE_MOUSE, InputDevice.KEYBOARD_TYPE_NONE, KeyEvent.KEYCODE_BACK))
    }

    @Test
    fun `keys of a button-only device stay with Android`() {
        assertFalse(
            DockedInput.isDesktopKey(false, InputDevice.SOURCE_KEYBOARD, InputDevice.KEYBOARD_TYPE_NON_ALPHABETIC, KeyEvent.KEYCODE_A),
        )
    }

    @Test
    fun `a press goes to X`() {
        assertTrue(DockedInput.dockedKeyToX(true, false))
    }

    @Test
    fun `a release whose press went to X goes to X`() {
        assertTrue(DockedInput.dockedKeyToX(false, true))
    }

    @Test
    fun `a release whose press went to Android goes to Android`() {
        assertFalse(DockedInput.dockedKeyToX(false, false))
    }
}
