export function timelineTime(row, runTime) {
  if (!row) return null;
  const explicit = row.valid_time || row.validTime || row.forecast_start;
  if (explicit && Number.isFinite(Date.parse(explicit))) return explicit;
  const run = Date.parse(runTime);
  return Number.isFinite(run) && Number.isFinite(Number(row.step))
    ? new Date(run + Number(row.step) * 3600000).toISOString() : null;
}

export function reconcileTimeline(rows, runTime, anchor, preferredStep = null) {
  const target = Date.parse(anchor?.validTime);
  const match = Number.isFinite(target)
    ? rows.find((row) => Date.parse(timelineTime(row, runTime)) === target) : null;
  // Jangan pernah memilih step yang belum ready: layer tidak akan tergambar.
  const ready = (row) => row && row.ready !== false;
  const chosen = (ready(match) ? match : null)
    || rows.find((row) => Number(row.step) === preferredStep && ready(row))
    || rows.find(ready) || rows[0];
  const messages = [];
  if (anchor?.runTime && Date.parse(anchor.runTime) !== Date.parse(runTime)) {
    messages.push('Run produk berbeda; waktu berlaku diselaraskan bila tersedia.');
  }
  if (Number.isFinite(target) && !match) {
    messages.push('Waktu sebelumnya tidak tersedia; pilihan berpindah ke waktu tersedia.');
  }
  return { step: chosen ? Number(chosen.step) : null, notice: messages.join(' ') };
}
