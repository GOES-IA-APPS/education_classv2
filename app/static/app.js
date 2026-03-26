document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const desktopQuery = window.matchMedia("(min-width: 1025px)");
  const toggleButtons = document.querySelectorAll("[data-sidebar-toggle]");
  const closeButtons = document.querySelectorAll("[data-sidebar-close]");
  const collapseButtons = document.querySelectorAll("[data-sidebar-collapse]");
  const collapseStorageKey = "education_classv2.sidebar.collapsed";

  const closeSidebar = () => body.classList.remove("sidebar-open");
  const openSidebar = () => body.classList.add("sidebar-open");
  const setCollapsed = (collapsed) => {
    body.classList.toggle("sidebar-collapsed", collapsed);
    try {
      window.localStorage.setItem(collapseStorageKey, collapsed ? "1" : "0");
    } catch (_) {
      // noop
    }
  };

  const toggleCollapsed = () => {
    if (!desktopQuery.matches) {
      return;
    }
    setCollapsed(!body.classList.contains("sidebar-collapsed"));
  };

  try {
    setCollapsed(window.localStorage.getItem(collapseStorageKey) === "1");
  } catch (_) {
    setCollapsed(false);
  }

  toggleButtons.forEach((button) => {
    button.addEventListener("click", () => {
      if (desktopQuery.matches) {
        toggleCollapsed();
        return;
      }
      if (body.classList.contains("sidebar-open")) {
        closeSidebar();
        return;
      }
      openSidebar();
    });
  });

  closeButtons.forEach((button) => {
    button.addEventListener("click", closeSidebar);
  });

  collapseButtons.forEach((button) => {
    button.addEventListener("click", toggleCollapsed);
  });

  const handleViewportChange = (event) => {
    if (!event.matches) {
      body.classList.remove("sidebar-collapsed");
      return;
    }
    try {
      setCollapsed(window.localStorage.getItem(collapseStorageKey) === "1");
    } catch (_) {
      setCollapsed(false);
    }
  };

  if (typeof desktopQuery.addEventListener === "function") {
    desktopQuery.addEventListener("change", handleViewportChange);
  } else if (typeof desktopQuery.addListener === "function") {
    desktopQuery.addListener(handleViewportChange);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSidebar();
    }
  });

  document.querySelectorAll(".table").forEach((table) => {
    if (!table.closest(".report-card-sheet")) {
      table.classList.add("auto-responsive");
    }

    const headers = Array.from(table.querySelectorAll("thead th")).map((header) =>
      (header.textContent || "").trim()
    );

    table.querySelectorAll("tbody tr").forEach((row) => {
      Array.from(row.children).forEach((cell, index) => {
        if (!cell.getAttribute("data-label") && headers[index]) {
          cell.setAttribute("data-label", headers[index]);
        }
      });
    });
  });

  const activeLinks = document.querySelectorAll(".nav a");
  activeLinks.forEach((link) => {
    const href = link.getAttribute("href");
    if (
      href &&
      (window.location.pathname === href ||
        (href !== "/dashboard" && window.location.pathname.startsWith(href)))
    ) {
      link.classList.add("is-active");
    }
  });
});
