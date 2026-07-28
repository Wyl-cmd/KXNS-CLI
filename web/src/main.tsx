import "./bootstrap";

if (import.meta.env.DEV) {
  import("react-scan")
    .then(({ scan }) => {
      scan({ enabled: true });
    })
    .catch(() => {
      // react-scan not available, skip
    });
}
