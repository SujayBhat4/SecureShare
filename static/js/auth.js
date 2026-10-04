// auth.js: logic for the login / sign up page (index.html)

const form = document.getElementById("auth-form");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const submitButton = document.getElementById("submit-btn");
const toggleButton = document.getElementById("toggle-password");

let mode = "login"; // "login" or "signup"

fillIcons();
document.getElementById("hero-logo").innerHTML = brandMark();
toggleButton.innerHTML = icon("eye");
emailInput.focus();

// If the visitor is already logged in, skip this page
api("GET", "/api/auth/me")
  .then(() => (window.location.href = "/static/app.html"))
  .catch(() => {}); // not logged in: stay here

// Switches between the Log in and Sign up tabs and changes the texts to match
function setMode(newMode) {
  mode = newMode;
  const isSignup = mode === "signup";
  document.getElementById("tab-login").classList.toggle("is-active", !isSignup);
  document.getElementById("tab-signup").classList.toggle("is-active", isSignup);
  document.getElementById("tab-login").setAttribute("aria-selected", String(!isSignup));
  document.getElementById("tab-signup").setAttribute("aria-selected", String(isSignup));
  document.getElementById("form-title").textContent = isSignup ? "Create your account" : "Welcome back";
  document.getElementById("form-sub").textContent = isSignup
    ? "Start sharing files safely in under a minute."
    : "Log in to manage your shared files.";
  submitButton.textContent = isSignup ? "Create account" : "Log in";
  passwordInput.autocomplete = isSignup ? "new-password" : "current-password";
  passwordInput.placeholder = isSignup ? "At least 8 characters" : "Your password";
  document.getElementById("password-hint").hidden = !isSignup;
  clearErrors();
  emailInput.focus();
}

// Shows or clears the small red message under a field
function setFieldError(name, message) {
  document.getElementById(`error-${name}`).textContent = message;
  document.getElementById(`field-${name}`).classList.toggle("has-error", message !== "");
}

function clearErrors() {
  setFieldError("email", "");
  setFieldError("password", "");
}

// Checks the form in the browser first so the user gets instant feedback.
// (The server checks again; the browser check is only for convenience.)
function validate() {
  clearErrors();
  let ok = true;
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(emailInput.value.trim())) {
    setFieldError("email", "Enter a valid email address");
    ok = false;
  }
  if (passwordInput.value === "") {
    setFieldError("password", "Enter your password");
    ok = false;
  } else if (mode === "signup" && passwordInput.value.length < 8) {
    setFieldError("password", "Password must be at least 8 characters");
    ok = false;
  }
  return ok;
}

document.getElementById("tab-login").addEventListener("click", () => setMode("login"));
document.getElementById("tab-signup").addEventListener("click", () => setMode("signup"));

// Show / hide the password
toggleButton.addEventListener("click", () => {
  const hidden = passwordInput.type === "password";
  passwordInput.type = hidden ? "text" : "password";
  toggleButton.innerHTML = icon(hidden ? "eyeOff" : "eye");
  toggleButton.setAttribute("aria-label", hidden ? "Hide password" : "Show password");
});

// Enter key or button click: send the form to the server
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!validate()) return;

  setLoading(submitButton, true);
  try {
    const path = mode === "signup" ? "/api/auth/signup" : "/api/auth/login";
    await api("POST", path, { email: emailInput.value.trim(), password: passwordInput.value });
    window.location.href = "/static/app.html";
  } catch (error) {
    showToast(error.message, "error");
    setLoading(submitButton, false);
  }
});
