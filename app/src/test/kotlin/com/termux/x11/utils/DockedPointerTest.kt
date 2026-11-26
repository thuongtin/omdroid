package com.termux.x11.utils

import android.view.MotionEvent
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/**
 * r8: docked mouse and touchpad events turned into X pointer input (termux-x11
 * submodule, `DockedPointer`). The event shapes follow AOSP 16's CursorInputMapper
 * (one frame = BUTTON_RELEASE, main event, BUTTON_PRESS, HOVER_MOVE after UP, SCROLL,
 * all carrying the frame's relative motion) and GestureConverter (two-finger scroll
 * as a fake finger classified TWO_FINGER_SWIPE).
 */
class DockedPointerTest {

    private class Recorder : DockedPointer.Sink {
        val ops = mutableListOf<String>()
        override fun move(dx: Float, dy: Float) {
            ops += "move $dx $dy"
        }

        override fun button(xButton: Int, down: Boolean) {
            ops += "button $xButton ${if (down) "down" else "up"}"
        }

        override fun wheel(dx: Float, dy: Float) {
            ops += "wheel $dx $dy"
        }
    }

    private val p = DockedPointer()
    private val r = Recorder()

    private fun ev(
        action: Int,
        buttons: Int = 0,
        relX: Float = 0f,
        relY: Float = 0f,
        vscroll: Float = 0f,
        hscroll: Float = 0f,
        classification: Int = MotionEvent.CLASSIFICATION_NONE,
        gx: Float = 0f,
        gy: Float = 0f,
    ) = p.onEvent(action, buttons, classification, relX, relY, vscroll, hscroll, gx, gy, r)

    @Test
    fun `hover motion moves X relatively`() {
        ev(MotionEvent.ACTION_HOVER_MOVE, relX = 12f, relY = -9f)
        assertEquals(listOf("move 12.0 -9.0"), r.ops)
    }

    @Test
    fun `a still hover sends nothing`() {
        ev(MotionEvent.ACTION_HOVER_MOVE)
        assertEquals(emptyList<String>(), r.ops)
    }

    @Test
    fun `a click is one press and one release`() {
        ev(MotionEvent.ACTION_DOWN, buttons = MotionEvent.BUTTON_PRIMARY)
        ev(MotionEvent.ACTION_BUTTON_PRESS, buttons = MotionEvent.BUTTON_PRIMARY)
        ev(MotionEvent.ACTION_BUTTON_RELEASE, buttons = 0)
        ev(MotionEvent.ACTION_UP, buttons = 0)
        ev(MotionEvent.ACTION_HOVER_MOVE, buttons = 0)
        assertEquals(listOf("button 1 down", "button 1 up"), r.ops)
    }

    @Test
    fun `motion in a click frame moves X once`() {
        // CursorInputMapper puts the frame's delta on DOWN and on BUTTON_PRESS
        ev(MotionEvent.ACTION_DOWN, buttons = MotionEvent.BUTTON_PRIMARY, relX = 3f, relY = 4f)
        ev(MotionEvent.ACTION_BUTTON_PRESS, buttons = MotionEvent.BUTTON_PRIMARY, relX = 3f, relY = 4f)
        assertEquals(listOf("move 3.0 4.0", "button 1 down"), r.ops)
    }

    @Test
    fun `motion in a release frame moves X once`() {
        ev(MotionEvent.ACTION_DOWN, buttons = MotionEvent.BUTTON_PRIMARY)
        r.ops.clear()
        // BUTTON_RELEASE, UP and the HOVER_MOVE after it all carry the delta
        ev(MotionEvent.ACTION_BUTTON_RELEASE, buttons = 0, relX = 5f, relY = 1f)
        ev(MotionEvent.ACTION_UP, buttons = 0, relX = 5f, relY = 1f)
        ev(MotionEvent.ACTION_HOVER_MOVE, buttons = 0, relX = 5f, relY = 1f)
        assertEquals(listOf("button 1 up", "move 5.0 1.0"), r.ops)
    }

    @Test
    fun `a drag moves with the button held`() {
        ev(MotionEvent.ACTION_DOWN, buttons = MotionEvent.BUTTON_PRIMARY)
        ev(MotionEvent.ACTION_MOVE, buttons = MotionEvent.BUTTON_PRIMARY, relX = 7f, relY = 0f)
        ev(MotionEvent.ACTION_UP, buttons = 0)
        assertEquals(listOf("button 1 down", "move 7.0 0.0", "button 1 up"), r.ops)
    }

    @Test
    fun `secondary and tertiary map to X right and middle`() {
        ev(MotionEvent.ACTION_BUTTON_PRESS, buttons = MotionEvent.BUTTON_SECONDARY)
        ev(MotionEvent.ACTION_BUTTON_RELEASE, buttons = 0)
        ev(MotionEvent.ACTION_BUTTON_PRESS, buttons = MotionEvent.BUTTON_TERTIARY)
        ev(MotionEvent.ACTION_BUTTON_RELEASE, buttons = 0)
        assertEquals(listOf("button 3 down", "button 3 up", "button 2 down", "button 2 up"), r.ops)
    }

    @Test
    fun `one wheel click up is one X click up`() {
        ev(MotionEvent.ACTION_SCROLL, vscroll = 1f)
        assertEquals(listOf("wheel 0.0 -120.0"), r.ops)
    }

    @Test
    fun `wheel down and tilt right are positive`() {
        ev(MotionEvent.ACTION_SCROLL, vscroll = -2f, hscroll = 1f)
        assertEquals(listOf("wheel 120.0 240.0"), r.ops)
    }

    @Test
    fun `a two-finger touchpad scroll is wheel, not a click`() {
        val swipe = MotionEvent.CLASSIFICATION_TWO_FINGER_SWIPE
        ev(MotionEvent.ACTION_DOWN, classification = swipe)
        ev(MotionEvent.ACTION_MOVE, classification = swipe, gx = 0f, gy = 30f)
        ev(MotionEvent.ACTION_MOVE, classification = swipe, gx = -6f, gy = 0f)
        ev(MotionEvent.ACTION_UP, classification = swipe)
        assertEquals(listOf("wheel 0.0 30.0", "wheel -6.0 0.0"), r.ops)
        assertFalse(p.anyButtonHeld())
    }

    @Test
    fun `pinch and three-finger swipes are dropped`() {
        ev(MotionEvent.ACTION_MOVE, classification = MotionEvent.CLASSIFICATION_PINCH, relX = 4f)
        ev(MotionEvent.ACTION_MOVE, classification = DockedPointer.CLASSIFICATION_MULTI_FINGER_SWIPE, relX = 4f)
        assertEquals(emptyList<String>(), r.ops)
    }

    @Test
    fun `releaseAll lets go of every held button once`() {
        ev(MotionEvent.ACTION_DOWN, buttons = MotionEvent.BUTTON_PRIMARY or MotionEvent.BUTTON_SECONDARY)
        assertTrue(p.anyButtonHeld())
        r.ops.clear()
        p.releaseAll(r)
        p.releaseAll(r)
        assertEquals(listOf("button 1 up", "button 3 up"), r.ops)
        assertFalse(p.anyButtonHeld())
    }

    @Test
    fun `a cancelled stream releases the buttons`() {
        ev(MotionEvent.ACTION_DOWN, buttons = MotionEvent.BUTTON_PRIMARY)
        r.ops.clear()
        ev(MotionEvent.ACTION_CANCEL, buttons = MotionEvent.BUTTON_PRIMARY)
        assertEquals(listOf("button 1 up"), r.ops)
    }

    @Test
    fun `a touchpad tap-to-click is a click`() {
        // GestureConverter: DOWN + BUTTON_PRESS, then BUTTON_RELEASE + UP, relative axes 0
        ev(MotionEvent.ACTION_DOWN, buttons = MotionEvent.BUTTON_PRIMARY)
        ev(MotionEvent.ACTION_BUTTON_PRESS, buttons = MotionEvent.BUTTON_PRIMARY)
        ev(MotionEvent.ACTION_BUTTON_RELEASE, buttons = 0)
        ev(MotionEvent.ACTION_UP, buttons = 0)
        assertEquals(listOf("button 1 down", "button 1 up"), r.ops)
    }
}
