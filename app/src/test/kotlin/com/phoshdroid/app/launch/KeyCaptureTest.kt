package com.phoshdroid.app.launch

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class KeyCaptureTest {

    private val omdroid = "com.phoshdroid.app/com.termux.x11.utils.KeyInterceptor"
    private val talkback = "com.google.android.marvin.talkback/.TalkBackService"
    private val passwordManager = "com.example.vault/.AutofillService"

    @Test
    fun `null current becomes just the component`() {
        assertEquals(omdroid, KeyCapture.withService(null, omdroid))
    }

    @Test
    fun `empty current becomes just the component`() {
        assertEquals(omdroid, KeyCapture.withService("", omdroid))
    }

    @Test
    fun `already present alone is left alone`() {
        assertEquals(omdroid, KeyCapture.withService(omdroid, omdroid))
    }

    @Test
    fun `other services are kept`() {
        assertEquals("$talkback:$omdroid", KeyCapture.withService(talkback, omdroid))
    }

    @Test
    fun `several other services keep their order`() {
        assertEquals(
            "$talkback:$passwordManager:$omdroid",
            KeyCapture.withService("$talkback:$passwordManager", omdroid),
        )
    }

    @Test
    fun `an entry in the middle keeps its position`() {
        val current = "$talkback:$omdroid:$passwordManager"
        assertEquals(current, KeyCapture.withService(current, omdroid))
    }

    @Test
    fun `adding twice does not duplicate the component`() {
        val once = KeyCapture.withService(talkback, omdroid)
        assertEquals(once, KeyCapture.withService(once, omdroid))
        assertEquals(2, once.split(':').size, "one colon = two entries")
    }
}
