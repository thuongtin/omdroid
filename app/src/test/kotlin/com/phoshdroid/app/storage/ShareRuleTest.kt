package com.phoshdroid.app.storage

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ShareRuleTest {

    @Test
    fun `auto follows the grant`() {
        assertTrue(ShareRule.resolve("auto", allFilesGranted = true))
        assertFalse(ShareRule.resolve("auto", allFilesGranted = false))
    }

    @Test
    fun `an unset preference is auto`() {
        assertEquals("auto", ShareRule.normalise(null))
        assertEquals("auto", ShareRule.normalise("nonsense"))
        assertTrue(ShareRule.resolve(null, allFilesGranted = true))
        assertFalse(ShareRule.resolve(null, allFilesGranted = false))
    }

    @Test
    fun `an explicit choice wins over the grant`() {
        assertTrue(ShareRule.resolve("on", allFilesGranted = false))
        assertFalse(ShareRule.resolve("off", allFilesGranted = true))
    }

    @Test
    fun `the old boolean switch becomes an explicit mode`() {
        assertEquals("on", ShareRule.modeFor(null, legacy = true))
        assertEquals("off", ShareRule.modeFor(null, legacy = false))
        assertEquals("auto", ShareRule.modeFor(null, legacy = null))
        assertNull(ShareRule.fromLegacy(null))
    }

    @Test
    fun `a stored tri-state beats the old switch`() {
        assertEquals("auto", ShareRule.modeFor("auto", legacy = true))
    }
}
