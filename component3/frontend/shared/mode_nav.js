"use strict";

(async () => {
  const nav = document.getElementById("mode-nav");
  if (!nav) return;
  try {
    const response = await fetch("/api/dashboard/config");
    if (!response.ok) throw new Error(`Dashboard mode unavailable (${response.status})`);
    const config = await response.json();
    config.navigation.forEach((item) => {
      const link = document.createElement("a");
      link.href = item.path;
      link.textContent = item.label;
      if (location.pathname === item.path) link.setAttribute("aria-current", "page");
      nav.append(link);
    });
  } catch (error) {
    nav.textContent = error.message;
  }
})();
