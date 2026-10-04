// api.js: one small wrapper around fetch() so every page talks to the server the same way.

// Turns the server's error body into one readable sentence.
// FastAPI sends {"detail": "message"} for our errors and a list of problems for invalid input.
function errorMessage(data, fallback) {
  if (!data || !data.detail) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail.length > 0) {
    const first = data.detail[0];
    const field = first.loc ? first.loc[first.loc.length - 1] : "";
    return field ? `${field}: ${first.msg}` : first.msg;
  }
  return fallback;
}

// Sends a JSON request and returns the parsed JSON answer.
// On an error it throws an Error whose message is the server's "detail" text,
// so callers can simply show error.message in a toast.
async function api(method, path, body) {
  const options = { method: method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(path, options);
  } catch (networkError) {
    throw new Error("Cannot reach the server. Check your connection and try again.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch (notJson) {
    // Some answers have no body; that is fine.
  }

  if (!response.ok) {
    // Session expired while using the app: go back to the login page
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      window.location.href = "/static/index.html";
    }
    const error = new Error(errorMessage(data, `Something went wrong (${response.status})`));
    error.status = response.status;
    throw error;
  }
  return data;
}

// Uploads a file with XMLHttpRequest (fetch cannot report upload progress).
// onProgress receives a number from 0 to 100.
function uploadFile(file, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("upload", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/files");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch (notJson) {
        // ignore
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        reject(new Error(errorMessage(data, `Upload failed (${xhr.status})`)));
      }
    };
    xhr.onerror = () => reject(new Error("Cannot reach the server. Check your connection and try again."));
    xhr.send(form);
  });
}
