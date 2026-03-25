document.addEventListener("DOMContentLoaded", () => {
  const activeLinks = document.querySelectorAll(".nav a");
  activeLinks.forEach((link) => {
    const href = link.getAttribute("href");
    if (
      window.location.pathname === href ||
      (href !== "/dashboard" && window.location.pathname.startsWith(href))
    ) {
      link.classList.add("is-active");
    }
  });
});
