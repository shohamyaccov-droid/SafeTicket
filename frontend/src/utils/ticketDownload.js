function filenameFromContentDisposition(headers = {}) {
  const disp = String(
    headers['content-disposition'] || headers['Content-Disposition'] || ''
  );
  const starMatch = /filename\*=UTF-8''([^;\s]+)/i.exec(disp);
  const quotedMatch = /filename="([^"]*)"/i.exec(disp);
  const plainMatch = /filename=([^;\s]+)/i.exec(disp);
  if (starMatch) {
    try {
      return decodeURIComponent(starMatch[1].replace(/["']/g, ''));
    } catch {
      return starMatch[1];
    }
  }
  if (quotedMatch) return quotedMatch[1];
  if (plainMatch) return plainMatch[1].replace(/^["']|["']$/g, '');
  return null;
}

function extensionFromMime(mime) {
  if (mime === 'application/pdf') return '.pdf';
  if (mime === 'image/jpeg' || mime === 'image/jpg') return '.jpg';
  if (mime === 'image/png') return '.png';
  if (mime === 'image/webp') return '.webp';
  if (mime === 'image/gif') return '.gif';
  if (mime === 'text/html') return '.html';
  return '';
}

function hasExtension(name) {
  return typeof name === 'string' && /\.[a-z0-9]{2,8}$/i.test(name.trim());
}

function mimeFromAxiosHeaders(headers = {}) {
  const rawType =
    headers['content-type'] ||
    headers['Content-Type'] ||
    'application/octet-stream';
  return String(rawType).split(';')[0].trim().toLowerCase();
}

export function openBlobForMobile(blob, options = {}) {
  const { downloadName = '', target = '_blank' } = options;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.target = target;
  link.rel = 'noopener noreferrer';
  if (downloadName) {
    link.download = downloadName;
  }

  try {
    document.body.appendChild(link);
    link.click();
  } catch {
    window.location.assign(url);
  } finally {
    link.remove();
    // iOS Safari may not open/save object URLs if revoked immediately after click.
    window.setTimeout(() => window.URL.revokeObjectURL(url), 120_000);
  }
}

/**
 * Download ticket file from an axios blob response using server Content-Type
 * and Content-Disposition filename when present.
 *
 * @param {import('axios').AxiosResponse<Blob>} response
 * @param {{ ticketId?: string|number, index?: number|null }} [options]
 */
export function downloadTicketFromAxiosBlob(response, options = {}) {
  const { ticketId = 'ticket', index = null } = options;
  const headers = response.headers || {};
  const mime = mimeFromAxiosHeaders(headers);
  const serverName = filenameFromContentDisposition(headers);

  let downloadName = serverName && serverName.trim() ? serverName.trim() : null;
  if (!downloadName || !hasExtension(downloadName)) {
    const ext = extensionFromMime(mime) || '.bin';
    const base = index != null ? `ticket-${index + 1}` : `ticket-${ticketId}`;
    downloadName = `${base}${ext}`;
  }

  const blob = new Blob([response.data], {
    type: mime || 'application/octet-stream',
  });
  openBlobForMobile(blob, { downloadName });
}

export function openAxiosBlobForMobile(response, options = {}) {
  const headers = response.headers || {};
  const mime = mimeFromAxiosHeaders(headers);
  const serverName = filenameFromContentDisposition(headers);
  const fallbackName = options.fallbackName || 'download';
  const baseName = serverName || fallbackName;
  const downloadName = hasExtension(baseName)
    ? baseName
    : `${baseName}${extensionFromMime(mime) || '.bin'}`;
  const blob = new Blob([response.data], {
    type: mime || 'application/octet-stream',
  });
  openBlobForMobile(blob, { downloadName });
}

/** MIME for Blob / previews from axios headers (blob response). */
export function ticketFileMimeFromAxiosHeaders(headers) {
  return mimeFromAxiosHeaders(headers);
}
