package com.phoshdroid.app.storage

import android.database.Cursor
import android.database.MatrixCursor
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.provider.DocumentsContract.Document
import android.provider.DocumentsContract.Root
import android.provider.DocumentsProvider
import android.webkit.MimeTypeMap
import com.phoshdroid.app.R
import com.phoshdroid.app.proot.ProotService
import java.io.File
import java.io.FileNotFoundException
import java.nio.file.Files

/**
 * The guest's home in Android's system file picker: one "Omdroid" root that reads and writes files
 * under `/home/omarchy` inside the guest rootfs (contract section 10).
 *
 * Paths are resolved by [GuestTree], not by `File.canonicalPath`: a symlink inside the guest holds
 * an absolute GUEST path, so a host-side resolve would either fail or leave the home. Everything
 * that resolves outside the home, or while the guest is not extracted, is refused.
 *
 * The manifest declaration is the one the platform documents for a custom provider
 * (https://developer.android.com/guide/topics/providers/create-document-provider): `exported="true"`,
 * `grantUriPermissions="true"`, `android:permission="android.permission.MANAGE_DOCUMENTS"` and an
 * intent filter for `android.content.action.DOCUMENTS_PROVIDER`.
 */
class OmdroidDocumentsProvider : DocumentsProvider() {
    override fun onCreate(): Boolean = true

    private fun tree(): GuestTree = GuestTree(rootfsDir())

    /** One line per provider call, so a device round can read what the picker really asked for. */
    private fun log(message: String) {
        android.util.Log.i("Phoshdroid", "documents: $message")
    }

    private fun rootfsDir(): File =
        File(
            requireNotNull(context).filesDir,
            "usr/var/lib/proot-distro/installed-rootfs/${ProotService.DISTRO_NAME}",
        )

    // ------------------------------------------------------------------ roots

    override fun queryRoots(projection: Array<out String>?): Cursor {
        val cursor = MatrixCursor(projection ?: DEFAULT_ROOT_PROJECTION)
        val tree = tree()
        if (!tree.extracted()) {
            log("queryRoots: guest not extracted, no root")
            return cursor
        }
        log("queryRoots: root=${tree.home}")
        val row = cursor.newRow()
        for (column in cursor.columnNames) {
            when (column) {
                Root.COLUMN_ROOT_ID -> row.add(ROOT_ID)
                Root.COLUMN_DOCUMENT_ID -> row.add(ROOT_ID)
                Root.COLUMN_TITLE -> row.add(context!!.getString(R.string.share_root_title))
                Root.COLUMN_SUMMARY -> row.add(context!!.getString(R.string.share_root_summary))
                Root.COLUMN_ICON -> row.add(R.mipmap.ic_launcher)
                Root.COLUMN_FLAGS ->
                    row.add(
                        Root.FLAG_LOCAL_ONLY or
                            Root.FLAG_SUPPORTS_CREATE or
                            Root.FLAG_SUPPORTS_IS_CHILD,
                    )
                Root.COLUMN_AVAILABLE_BYTES -> row.add(availableBytes())
                else -> row.add(null)
            }
        }
        return cursor
    }

    private fun availableBytes(): Long =
        try {
            android.os.StatFs(requireNotNull(context).filesDir.path).availableBytes
        } catch (_: Exception) {
            0L
        }

    // -------------------------------------------------------------- documents

    override fun queryDocument(documentId: String, projection: Array<out String>?): Cursor {
        log("queryDocument $documentId")
        val cursor = MatrixCursor(projection ?: DEFAULT_DOCUMENT_PROJECTION)
        includeDocument(cursor, documentId)
        return cursor
    }

    override fun queryChildDocuments(
        parentDocumentId: String,
        projection: Array<out String>?,
        sortOrder: String?,
    ): Cursor {
        val cursor = MatrixCursor(projection ?: DEFAULT_DOCUMENT_PROJECTION)
        val parentRelative = relativeOf(parentDocumentId) ?: return cursor
        val tree = tree()
        val parent = tree.resolve(parentRelative) ?: return cursor
        if (!parent.isDirectory) return cursor
        val children = tree.children(parentRelative)
        log(
            "children of '$parentDocumentId' (${parent.name}): ${children.size} " +
                children.take(5).map { it.name },
        )
        for (child in children) {
            val relative = if (parentRelative.isEmpty()) child.name else "$parentRelative/${child.name}"
            includeDocument(cursor, idOf(relative), child)
        }
        return cursor
    }

    override fun getDocumentType(documentId: String): String {
        val relative = relativeOf(documentId) ?: return OCTET_STREAM
        val file = tree().resolve(relative) ?: return OCTET_STREAM
        return if (file.isDirectory) Document.MIME_TYPE_DIR else mimeOf(file.name)
    }

    override fun isChildDocument(parentDocumentId: String, documentId: String): Boolean {
        val parent = relativeOf(parentDocumentId) ?: return false
        val child = relativeOf(documentId) ?: return false
        if (parent.isEmpty()) return true
        return child == parent || child.startsWith("$parent/")
    }

    private fun includeDocument(cursor: MatrixCursor, documentId: String, known: File? = null) {
        val relative = relativeOf(documentId) ?: throw FileNotFoundException(documentId)
        val tree = tree()
        val file = known ?: tree.resolve(relative) ?: throw FileNotFoundException(documentId)
        val isRoot = relative.isEmpty()
        val row = cursor.newRow()
        for (column in cursor.columnNames) {
            when (column) {
                Document.COLUMN_DOCUMENT_ID -> row.add(documentId)
                Document.COLUMN_DISPLAY_NAME ->
                    row.add(if (isRoot) context!!.getString(R.string.share_root_title) else file.name)
                Document.COLUMN_MIME_TYPE ->
                    row.add(if (file.isDirectory) Document.MIME_TYPE_DIR else mimeOf(file.name))
                Document.COLUMN_SIZE -> row.add(if (file.isDirectory) 0L else file.length())
                Document.COLUMN_LAST_MODIFIED -> row.add(file.lastModified())
                Document.COLUMN_FLAGS -> row.add(
                    when {
                        isRoot -> Document.FLAG_DIR_SUPPORTS_CREATE
                        file.isDirectory ->
                            Document.FLAG_DIR_SUPPORTS_CREATE or
                                Document.FLAG_SUPPORTS_DELETE or
                                Document.FLAG_SUPPORTS_RENAME
                        else ->
                            Document.FLAG_SUPPORTS_WRITE or
                                Document.FLAG_SUPPORTS_DELETE or
                                Document.FLAG_SUPPORTS_RENAME
                    },
                )
                else -> row.add(null)
            }
        }
    }

    // ------------------------------------------------------------------- file

    override fun openDocument(
        documentId: String,
        mode: String,
        signal: CancellationSignal?,
    ): ParcelFileDescriptor {
        val relative = relativeOf(documentId) ?: throw FileNotFoundException(documentId)
        val file = tree().resolve(relative) ?: throw FileNotFoundException(documentId)
        if (file.isDirectory) throw FileNotFoundException(documentId)
        if (!file.exists() && !mode.contains('w') && !mode.contains('t')) {
            throw FileNotFoundException(documentId)
        }
        log("openDocument $documentId mode=$mode -> $file")
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.parseMode(mode))
    }

    // ----------------------------------------------------------------- writes

    override fun createDocument(
        parentDocumentId: String,
        mimeType: String,
        displayName: String,
    ): String {
        val parentRelative = relativeOf(parentDocumentId) ?: throw FileNotFoundException(parentDocumentId)
        val parent = tree().resolve(parentRelative) ?: throw FileNotFoundException(parentDocumentId)
        if (!parent.isDirectory) throw FileNotFoundException(parentDocumentId)
        val name = uniqueName(parent, sanitiseName(displayName, mimeType))
        val created =
            if (mimeType == Document.MIME_TYPE_DIR) {
                File(parent, name).apply { if (!mkdirs()) throw IllegalStateException("mkdir $name") }
            } else {
                File(parent, name).apply { if (!createNewFile()) throw IllegalStateException("create $name") }
            }
        val relative = if (parentRelative.isEmpty()) created.name else "$parentRelative/${created.name}"
        log("createDocument in '$parentDocumentId' name=$name -> $relative")
        return idOf(relative)
    }

    override fun deleteDocument(documentId: String) {
        val relative = relativeOf(documentId) ?: throw FileNotFoundException(documentId)
        if (relative.isEmpty()) throw FileNotFoundException(documentId)
        val tree = tree()
        val file = tree.resolve(relative) ?: throw FileNotFoundException(documentId)
        log("deleteDocument $documentId -> $file")
        if (!deleteTree(file)) throw FileNotFoundException(documentId)
    }

    override fun renameDocument(documentId: String, displayName: String): String {
        val relative = relativeOf(documentId) ?: throw FileNotFoundException(documentId)
        if (relative.isEmpty()) throw FileNotFoundException(documentId)
        val tree = tree()
        val source = tree.resolve(relative) ?: throw FileNotFoundException(documentId)
        val parentRelative = relative.substringBeforeLast('/', "")
        val parent = tree.resolve(parentRelative) ?: throw FileNotFoundException(documentId)
        val name = uniqueName(parent, sanitiseName(displayName, mimeOf(source.name)))
        val target = File(parent, name)
        if (!source.renameTo(target)) throw IllegalStateException("rename ${source.name}")
        val renamed = if (parentRelative.isEmpty()) name else "$parentRelative/$name"
        return idOf(renamed)
    }

    /** Delete without ever following a symlink: the link goes, its target stays. */
    private fun deleteTree(file: File): Boolean {
        if (Files.isSymbolicLink(file.toPath())) return file.delete()
        if (file.isDirectory) {
            val entries = file.listFiles() ?: return false
            for (entry in entries) {
                if (!deleteTree(entry)) return false
            }
        }
        return file.delete()
    }

    private fun uniqueName(parent: File, requested: String): String {
        if (!File(parent, requested).exists()) return requested
        val base = requested.substringBeforeLast('.', requested)
        val extension = requested.removePrefix(base)
        var index = 2
        while (true) {
            val candidate = "$base ($index)$extension"
            if (!File(parent, candidate).exists()) return candidate
            index++
        }
    }

    /** A display name that is a plain file name: no separators, no traversal, no control bytes. */
    private fun sanitiseName(displayName: String, mimeType: String): String {
        var name = displayName.filter { it.code >= 0x20 && it != '/' && it != '\\' }
        name = name.trim().trim('.')
        if (name.isEmpty()) name = context!!.getString(R.string.share_new_document)
        if (name.length > 120) name = name.take(120)
        if (mimeType != Document.MIME_TYPE_DIR && !name.contains('.')) {
            val extension = MimeTypeMap.getSingleton().getExtensionFromMimeType(mimeType)
            if (!extension.isNullOrEmpty()) name = "$name.$extension"
        }
        return name
    }

    private fun mimeOf(name: String): String {
        val extension = name.substringAfterLast('.', "").lowercase()
        if (extension.isEmpty()) return OCTET_STREAM
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension) ?: OCTET_STREAM
    }

    // ------------------------------------------------------------ document ids

    private fun relativeOf(documentId: String): String? =
        when {
            documentId == ROOT_ID -> ""
            documentId.startsWith(PREFIX) -> documentId.removePrefix(PREFIX)
            else -> null
        }

    private fun idOf(relative: String): String = if (relative.isEmpty()) ROOT_ID else PREFIX + relative

    companion object {
        const val AUTHORITY = "com.phoshdroid.app.documents"
        const val ROOT_ID = "root"

        private const val PREFIX = "doc:"
        private const val OCTET_STREAM = "application/octet-stream"

        private val DEFAULT_ROOT_PROJECTION =
            arrayOf(
                Root.COLUMN_ROOT_ID,
                Root.COLUMN_DOCUMENT_ID,
                Root.COLUMN_TITLE,
                Root.COLUMN_SUMMARY,
                Root.COLUMN_ICON,
                Root.COLUMN_FLAGS,
                Root.COLUMN_AVAILABLE_BYTES,
            )

        private val DEFAULT_DOCUMENT_PROJECTION =
            arrayOf(
                Document.COLUMN_DOCUMENT_ID,
                Document.COLUMN_DISPLAY_NAME,
                Document.COLUMN_MIME_TYPE,
                Document.COLUMN_SIZE,
                Document.COLUMN_LAST_MODIFIED,
                Document.COLUMN_FLAGS,
            )
    }
}
