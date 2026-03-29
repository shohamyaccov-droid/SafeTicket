import toast from 'react-hot-toast';

const base = {
  duration: 4000,
  style: {
    direction: 'rtl',
    fontFamily: "'Assistant', 'Heebo', sans-serif",
    maxWidth: 'min(92vw, 420px)',
  },
};

export function toastSuccess(message) {
  return toast.success(message, { ...base, iconTheme: { primary: '#10b981', secondary: '#fff' } });
}

export function toastError(message) {
  return toast.error(message, { ...base, iconTheme: { primary: '#dc2626', secondary: '#fff' } });
}

export function toastLoading(message) {
  return toast.loading(message, base);
}

export function toastPromise(promise, msgs) {
  return toast.promise(promise, msgs, base);
}
