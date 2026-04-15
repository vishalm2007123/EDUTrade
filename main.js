document.addEventListener("DOMContentLoaded", function () {

  const hamburger = document.querySelector(".nav-hamburger");
  const navLinks = document.querySelector(".navbar-links");
  if (hamburger && navLinks) {
    hamburger.addEventListener("click", function () {
      navLinks.classList.toggle("open");
    });
    document.addEventListener("click", function (e) {
      if (!hamburger.contains(e.target) && !navLinks.contains(e.target)) {
        navLinks.classList.remove("open");
      }
    });
  }

  document.querySelectorAll(".alert-close").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const alert = btn.closest(".alert");
      if (alert) {
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-6px)";
        alert.style.transition = "all 0.2s ease";
        setTimeout(function () { alert.remove(); }, 200);
      }
    });
  });

  setTimeout(function () {
    document.querySelectorAll(".alert").forEach(function (alert) {
      if (!alert.querySelector(".alert-close")) return;
      alert.style.opacity = "0";
      alert.style.transform = "translateY(-6px)";
      alert.style.transition = "all 0.4s ease";
      setTimeout(function () { alert.remove(); }, 400);
    });
  }, 5000);

  document.querySelectorAll(".tab-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const tabId = btn.getAttribute("data-tab");
      const container = btn.closest(".tabs-container") || document;

      container.querySelectorAll(".tab-btn").forEach(function (b) {
        b.classList.remove("active");
      });
      container.querySelectorAll(".tab-panel").forEach(function (p) {
        p.classList.remove("active");
      });

      btn.classList.add("active");
      const panel = document.getElementById(tabId);
      if (panel) {
        panel.classList.add("active");
        panel.classList.add("fade-in");
      }
    });
  });

  const bidInput = document.getElementById("bid-amount-input");
  const bidRange = document.getElementById("bid-range");
  if (bidInput && bidRange) {
    bidRange.addEventListener("input", function () {
      bidInput.value = bidRange.value;
    });
    bidInput.addEventListener("input", function () {
      bidRange.value = bidInput.value;
    });
  }

  const coinEl = document.getElementById("navbar-coin-count");
  if (coinEl) {
    fetch("/api/coins")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        coinEl.textContent = data.coins.toLocaleString();
        coinEl.classList.add("coin-bounce");
      })
      .catch(function () {});
  }

  document.querySelectorAll(".confirm-action").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      const msg = form.getAttribute("data-confirm") || "Are you sure?";
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  document.querySelectorAll(".fade-in-card").forEach(function (el, idx) {
    el.style.opacity = "0";
    el.style.transform = "translateY(12px)";
    el.style.transition = "all 0.3s ease";
    setTimeout(function () {
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    }, idx * 60);
  });

  const skillSearch = document.getElementById("skill-search-input");
  if (skillSearch) {
    skillSearch.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        document.getElementById("skill-search-form").submit();
      }
    });
  }

  const charLimitFields = document.querySelectorAll("[data-maxlength]");
  charLimitFields.forEach(function (field) {
    const max = parseInt(field.getAttribute("data-maxlength"));
    const counterId = field.getAttribute("data-counter");
    const counter = document.getElementById(counterId);
    if (counter) {
      counter.textContent = max - field.value.length + " chars left";
      field.addEventListener("input", function () {
        const remaining = max - field.value.length;
        counter.textContent = remaining + " chars left";
        counter.style.color = remaining < 20 ? "#ef4444" : "var(--text-muted)";
      });
    }
  });

  const passwordField = document.getElementById("password");
  const strengthBar = document.getElementById("password-strength");
  if (passwordField && strengthBar) {
    passwordField.addEventListener("input", function () {
      const val = passwordField.value;
      let strength = 0;
      if (val.length >= 8) strength++;
      if (/[A-Z]/.test(val)) strength++;
      if (/[0-9]/.test(val)) strength++;
      if (/[^A-Za-z0-9]/.test(val)) strength++;

      const colors = ["#ef4444", "#f59e0b", "#10b981", "#059669"];
      const labels = ["Weak", "Fair", "Good", "Strong"];
      const widths = ["25%", "50%", "75%", "100%"];

      if (val.length === 0) {
        strengthBar.style.display = "none";
      } else {
        strengthBar.style.display = "block";
        const bar = strengthBar.querySelector(".strength-fill");
        const label = strengthBar.querySelector(".strength-label");
        if (bar) {
          bar.style.width = widths[strength - 1] || "0%";
          bar.style.background = colors[strength - 1] || "#ef4444";
          bar.style.transition = "all 0.3s ease";
        }
        if (label) {
          label.textContent = labels[strength - 1] || "Weak";
          label.style.color = colors[strength - 1] || "#ef4444";
        }
      }
    });
  }

  const fileInput = document.getElementById("certificate-upload");
  const fileLabel = document.getElementById("file-label");
  if (fileInput && fileLabel) {
    fileInput.addEventListener("change", function () {
      if (fileInput.files.length > 0) {
        fileLabel.textContent = fileInput.files[0].name;
        fileLabel.style.color = "var(--success)";
      } else {
        fileLabel.textContent = "Choose certificate file (PDF, PNG, JPG)";
        fileLabel.style.color = "var(--text-secondary)";
      }
    });
  }

  const navLinks2 = document.querySelectorAll(".navbar-links a");
  const currentPath = window.location.pathname;
  navLinks2.forEach(function (link) {
    if (link.getAttribute("href") === currentPath) {
      link.classList.add("active");
    }
  });
});