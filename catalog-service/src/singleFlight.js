
export function createCoalescedFetch() {
  const inFlight = new Map();

  return async (key, fetcher) => {
    let task = inFlight.get(key);

    if (!task) {
      task = Promise.resolve().then(fetcher);
      inFlight.set(key, task);

      const cleanup = () => {
        if (inFlight.get(key) === task) {
          inFlight.delete(key);
        }
      };

      void task.then(cleanup, cleanup);
    }

    const response = await task;
    return response.clone();
  };
}
