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
  const rawType =
    headers['content-type'] ||
    headers['Content-Type'] ||
    'application/octet-stream';
  const mime = String(rawType).split(';')[0].trim().toLowerCase();
  const disp = String(
    headers['content-disposition'] || headers['Content-Disposition'] || ''
  );

  let serverName = null;
  const starMatch = /filename\*=UTF-8''([^;\s]+)/i.exec(disp);
  const quotedMatch = /filename="([^"]*)"/i.exec(disp);
  const plainMatch = /filename=([^;\s]+)/i.exec(disp);
  if (starMatch) {
    try {
      serverName = decodeURIComponent(starMatch[1].replace(/["']/g, ''));
    } catch {
      serverName = starMatch[1];
    }
  } else if (quotedMatch) {
    serverName = quotedMatch[1];
  } else if (plainMatch) {
    serverName = plainMatch[1].replace(/^["']|["']$/g, '');
  }

  const extFromMime = () => {
    if (mime === 'application/pdf') return '.pdf';
    if (mime === 'image/jpeg' || mime === 'image/jpg') return '.jpg';
    if (mime === 'image/png') return '.png';
    if (mime === 'image/webp') return '.webp';
    if (mime === 'image/gif') return '.gif';
    return '';
  };

  const hasExtension = (name) =>
    typeof name === 'string' && /\.[a-z0-9]{2,8}$/i.test(name.trim());

  let downloadName = serverName && serverName.trim() ? serverName.trim() : null;
  if (!downloadName || !hasExtension(downloadName)) {
    const ext = extFromMime() || '.bin';
    const base = index != null ? `ticket-${index + 1}` : `ticket-${ticketId}`;
    downloadName = `${base}${ext}`;
  }

  const blob = new Blob([response.data], {
    type: mime || 'application/octet-stream',
  });
  const url = window.URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = downloadName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    window.URL.revokeObjectURL(url);
  }
}

/** MIME for Blob / previews from axios headers (blob response). */
export function ticketFileMimeFromAxiosHeaders(headers) {
  const h = headers || {};
  const raw =
    h['content-type'] || h['Content-Type'] || 'application/octet-stream';
  return String(raw).split(';')[0].trim().toLowerCase();
}
