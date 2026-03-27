/** Client-side cap for cold starts / hung connections — shows retry UI instead of infinite spinner */
export const LIST_FETCH_TIMEOUT_MS = 28000;

export function createListFetchAbort() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), LIST_FETCH_TIMEOUT_MS);
  const clear = () => clearTimeout(timer);
  return { signal: controller.signal, abort: () => controller.abort(), clear };
}
