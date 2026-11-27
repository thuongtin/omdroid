package com.phoshdroid.app.settings

/**
 * The snapshot the guest reads: every field's last reading, and when the host observed it.
 *
 * The host rewrites `state.json` only when a reading changes, or when a reading has aged far
 * enough that the guest would expire it ([REFRESH_MS] under [FIELD_TTL_MS]). Because every field
 * carries its own observation time, a host that stops publishing expires field by field without
 * the file ever being rewritten, and a desktop whose radios never change costs one write every
 * [REFRESH_MS] instead of one every two seconds.
 *
 * The JSON is written by hand: the field names are this class's own callers' literals and the
 * values are booleans, integers or null, so nothing here needs escaping.
 */
class AndroidState {
    private class Reading(val value: Any?, val at: Long)

    private val readings = LinkedHashMap<String, Reading>()

    /**
     * Records one observation of every field at [now] and reports whether the published JSON
     * changed: a new value, a new field, or an unchanged reading old enough to be re-confirmed.
     */
    fun observe(
        values: Map<String, Any?>,
        now: Long,
    ): Boolean {
        var changed = false
        for ((name, value) in values) {
            val previous = readings[name]
            // Unchanged and still inside the refresh window: the published JSON stays as it is.
            if (previous != null && previous.value == value && now - previous.at < REFRESH_MS) continue
            readings[name] = Reading(value, now)
            changed = true
        }
        return changed
    }

    /** The snapshot body, stamped with the time it is written. */
    fun json(timestamp: Long): String {
        val out = StringBuilder(320)
        out.append("{\"schema\":").append(SCHEMA)
        out.append(",\"timestamp\":").append(timestamp)
        out.append(",\"observed\":{")
        readings.entries.forEachIndexed { index, (name, reading) ->
            if (index > 0) out.append(',')
            out.append('"').append(name).append("\":").append(reading.at)
        }
        out.append('}')
        for ((name, reading) in readings) {
            out.append(",\"").append(name).append("\":")
            when (val value = reading.value) {
                is Boolean -> out.append(value)
                is Int -> out.append(value)
                else -> out.append("null")
            }
        }
        return out.append('}').toString()
    }

    fun clear() = readings.clear()

    companion object {
        /** Schema version the guest's `AndroidModel.js` accepts (contract section 13). */
        const val SCHEMA = 2

        /** How long the guest trusts a field after the host observed it. */
        const val FIELD_TTL_MS = 10_000L

        /** The host re-confirms every reading at this age, inside [FIELD_TTL_MS]. */
        const val REFRESH_MS = 8_000L
    }
}
