import toast from 'react-hot-toast';

const base = {
  duration: 4000,
  style: {
    direction: 'rtl',
    fontFamily: "'Assistant', 'Heebo', sans-serif",
    maxWidth: 'min(92vw, 420px)',
  },
};

export function toastSuccess(message, opts = {}) {
  return toast.success(message, {
    ...base,
    ...opts,
    style: { ...base.style, ...opts.style },
    iconTheme: { primary: '#10b981', secondary: '#fff' },
  });
}

export function toastError(message, opts = {}) {
  return toast.error(message, {
    ...base,
    ...opts,
    style: { ...base.style, ...opts.style },
    iconTheme: { primary: '#dc2626', secondary: '#fff' },
  });
}

export function toastLoading(message) {
  return toast.loading(message, base);
}

export function toastPromise(promise, msgs) {
  return toast.promise(promise, msgs, base);
}
