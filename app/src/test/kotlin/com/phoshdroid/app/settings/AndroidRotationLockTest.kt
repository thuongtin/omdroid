package com.phoshdroid.app.settings

import android.content.pm.ActivityInfo
import android.content.res.Configuration
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class AndroidRotationLockTest {
    private val portrait = Configuration.ORIENTATION_PORTRAIT
    private val landscape = Configuration.ORIENTATION_LANDSCAPE

    @Test fun `portrait natural displays keep all four orientations`() {
        assertEquals("portrait", AndroidRotationLock.currentPreference(portrait, 0, false))
        assertEquals("landscape", AndroidRotationLock.currentPreference(landscape, 1, false))
        assertEquals("reverse portrait", AndroidRotationLock.currentPreference(portrait, 2, false))
        assertEquals("reverse landscape", AndroidRotationLock.currentPreference(landscape, 3, false))
    }

    @Test fun `landscape natural tablets keep all four orientations`() {
        assertEquals("landscape", AndroidRotationLock.currentPreference(landscape, 0, false))
        assertEquals("reverse portrait", AndroidRotationLock.currentPreference(portrait, 1, false))
        assertEquals("reverse landscape", AndroidRotationLock.currentPreference(landscape, 2, false))
        assertEquals("portrait", AndroidRotationLock.currentPreference(portrait, 3, false))
    }

    @Test fun `OEM reverse default rotation is honored`() {
        assertEquals("reverse landscape", AndroidRotationLock.currentPreference(landscape, 1, true))
        assertEquals("landscape", AndroidRotationLock.currentPreference(landscape, 3, true))
        assertEquals("portrait", AndroidRotationLock.currentPreference(portrait, 1, true))
        assertEquals("reverse portrait", AndroidRotationLock.currentPreference(portrait, 3, true))
    }

    @Test fun `unknown geometry cannot silently lock to a different orientation`() {
        assertNull(AndroidRotationLock.currentPreference(Configuration.ORIENTATION_UNDEFINED, 0, false))
        assertNull(AndroidRotationLock.currentPreference(portrait, -1, false))
        assertNull(AndroidRotationLock.currentPreference(portrait, 4, false))
    }

    @Test fun `state follows the embedded display preference and unknown stays unknown`() {
        assertEquals(false, AndroidRotationLock.locked("auto"))
        for (value in listOf("portrait", "landscape", "reverse portrait", "reverse landscape")) {
            assertEquals(true, AndroidRotationLock.locked(value))
        }
        assertNull(AndroidRotationLock.locked(null))
        assertNull(AndroidRotationLock.locked("unexpected"))
    }

    @Test fun `unlock returns to system rotation and reverse locks use the correct activity request`() {
        assertEquals(ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED, AndroidRotationLock.requestedOrientation("auto"))
        assertEquals(ActivityInfo.SCREEN_ORIENTATION_REVERSE_PORTRAIT, AndroidRotationLock.requestedOrientation("reverse portrait"))
        assertEquals(ActivityInfo.SCREEN_ORIENTATION_REVERSE_LANDSCAPE, AndroidRotationLock.requestedOrientation("reverse landscape"))
    }

    @Test fun `only a zero auto-rotate switch reads as locked`() {
        assertEquals(true, AndroidRotationLock.lockedFromSetting(0))
        assertEquals(false, AndroidRotationLock.lockedFromSetting(1))
        assertNull(AndroidRotationLock.lockedFromSetting(null))
        assertNull(AndroidRotationLock.lockedFromSetting(-1))
        assertNull(AndroidRotationLock.lockedFromSetting(2))
    }

    @Test fun `either mechanism holding the orientation is locked and unknown stays unknown`() {
        assertEquals(true, AndroidRotationLock.combinedLocked(true, false))
        assertEquals(true, AndroidRotationLock.combinedLocked(false, true))
        assertEquals(false, AndroidRotationLock.combinedLocked(false, false))
        assertNull(AndroidRotationLock.combinedLocked(null, false))
        assertNull(AndroidRotationLock.combinedLocked(false, null))
        assertNull(AndroidRotationLock.combinedLocked(null, null))
    }

    @Test fun `a refused or ignored rotation write is not success`() {
        // No WRITE_SETTINGS app-op: Settings.System.putInt throws instead of writing.
        val refused = AndroidRotationLock.applyAndConfirm(
            0,
            { throw SecurityException("Disallowed call for uid 10243") },
            { 1 },
        )
        assertTrue(refused.isFailure)
        assertEquals("Disallowed call for uid 10243", refused.exceptionOrNull()?.message)
        // The call is accepted and the platform does nothing: only the read-back can tell.
        val ignored = AndroidRotationLock.applyAndConfirm(0, { }, { 1 })
        assertTrue(ignored.isFailure)
        // A switch that cannot be read back cannot confirm a write either.
        assertTrue(AndroidRotationLock.applyAndConfirm(0, { }, { null }).isFailure)
        // What Android did confirm is returned as the written value.
        assertEquals(0, AndroidRotationLock.applyAndConfirm(0, { }, { 0 }).getOrNull())
        assertEquals(1, AndroidRotationLock.applyAndConfirm(1, { }, { 1 }).getOrNull())
    }
}
