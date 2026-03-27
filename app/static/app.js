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

  const toastStack = document.createElement("div");
  toastStack.className = "ui-toast-stack";
  document.body.appendChild(toastStack);

  const toastTitles = {
    success: "Operación completada",
    error: "No se pudo completar la operación",
    warning: "Revisión requerida",
    info: "Aviso del sistema",
  };

  const showToast = (type, message) => {
    if (!message) {
      return;
    }

    const toast = document.createElement("div");
    toast.className = `ui-toast ${type || "info"}`;
    toast.innerHTML = `
      <strong>${toastTitles[type] || toastTitles.info}</strong>
      <p>${message}</p>
    `;
    toastStack.appendChild(toast);
    window.requestAnimationFrame(() => toast.classList.add("is-visible"));

    window.setTimeout(() => {
      toast.classList.remove("is-visible");
      window.setTimeout(() => toast.remove(), 220);
    }, 3200);
  };

  const flashNode = document.querySelector("[data-ui-flash]");
  if (flashNode) {
    showToast(flashNode.dataset.uiFlashType || "info", flashNode.dataset.uiFlashMessage || "");
  }

  const confirmDialog = document.createElement("div");
  confirmDialog.className = "ui-confirm";
  confirmDialog.innerHTML = `
    <div class="ui-confirm-backdrop" data-ui-confirm-close></div>
    <div class="ui-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="ui-confirm-title">
      <h3 id="ui-confirm-title">¿Estás seguro que lo quieres eliminar?</h3>
      <p>Escribe DELETE para poder eliminarlo.</p>
      <input type="text" autocomplete="off" spellcheck="false" data-ui-confirm-input placeholder="DELETE">
      <div class="ui-confirm-error" data-ui-confirm-error></div>
      <div class="ui-confirm-actions">
        <button type="button" class="button secondary" data-ui-confirm-cancel>Cancelar</button>
        <button type="button" class="button danger" data-ui-confirm-submit>Eliminar</button>
      </div>
    </div>
  `;
  document.body.appendChild(confirmDialog);

  const confirmInput = confirmDialog.querySelector("[data-ui-confirm-input]");
  const confirmError = confirmDialog.querySelector("[data-ui-confirm-error]");
  const confirmCancel = confirmDialog.querySelector("[data-ui-confirm-cancel]");
  const confirmSubmit = confirmDialog.querySelector("[data-ui-confirm-submit]");
  const confirmCloseNodes = confirmDialog.querySelectorAll("[data-ui-confirm-close]");

  const openDeleteConfirmation = (form) =>
    new Promise((resolve) => {
      confirmInput.value = "";
      confirmError.textContent = "";
      confirmDialog.classList.add("is-visible");
      window.setTimeout(() => confirmInput.focus(), 10);

      const cleanup = (result) => {
        confirmDialog.classList.remove("is-visible");
        confirmCancel.removeEventListener("click", onCancel);
        confirmSubmit.removeEventListener("click", onSubmit);
        confirmInput.removeEventListener("keydown", onKeydown);
        confirmCloseNodes.forEach((node) => node.removeEventListener("click", onCancel));
        resolve(result);
      };

      const onCancel = () => cleanup("cancel");
      const onSubmit = () => {
        if (confirmInput.value !== "DELETE") {
          confirmError.textContent = "Debes escribir DELETE exactamente para continuar.";
          confirmInput.focus();
          confirmInput.select();
          return;
        }
        const hiddenInput = form.querySelector('input[name="delete_confirmation"]');
        if (hiddenInput) {
          hiddenInput.value = "DELETE";
        }
        cleanup("confirm");
      };
      const onKeydown = (event) => {
        if (event.key === "Escape") {
          cleanup("cancel");
        }
        if (event.key === "Enter") {
          event.preventDefault();
          onSubmit();
        }
      };

      confirmCancel.addEventListener("click", onCancel);
      confirmSubmit.addEventListener("click", onSubmit);
      confirmInput.addEventListener("keydown", onKeydown);
      confirmCloseNodes.forEach((node) => node.addEventListener("click", onCancel));
    });

  document.querySelectorAll("form[data-delete-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      if (form.dataset.deleteConfirmed === "1") {
        return;
      }

      event.preventDefault();
      const result = await openDeleteConfirmation(form);
      if (result === "confirm") {
        form.dataset.deleteConfirmed = "1";
        form.submit();
        return;
      }
      if (result === "cancel") {
        showToast("info", "La eliminación fue cancelada.");
        return;
      }
      showToast("warning", "Debes escribir DELETE exactamente para eliminar.");
    });
  });
});
