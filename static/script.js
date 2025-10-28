const apiBase = ""; // backend URL
let userEmail = "";

// Toast
function showToast(message, success = true) {
  const toast = document.getElementById("toast");
  toast.innerText = message;
  toast.style.background = success ? "#4BB543" : "#E74C3C";
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 3000);
}

// Bangladesh time
function getBDTime() {
  const now = new Date();
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  const bdOffset = 6 * 60 * 60 * 1000;
  const bdDate = new Date(utc + bdOffset);
  let hours = bdDate.getHours();
  const minutes = bdDate.getMinutes();
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  const minStr = minutes < 10 ? "0" + minutes : minutes;
  return `${hours}:${minStr} ${ampm}`;
}

// Google Sign-In
function handleCredentialResponse(response) {
  const data = jwt_decode(response.credential);
  userEmail = data.email;

  document.getElementById("email").value = userEmail;
  document.getElementById("attForm").classList.remove("hidden");
  document.getElementById("googleSignInBtn").style.display = "none";

  document.getElementById("time_now").value = getBDTime();
  loadEmployeeInfo(userEmail);
}

window.onload = function () {
  google.accounts.id.initialize({
    client_id: "YOUR_CLIENT_ID_HERE",
    callback: handleCredentialResponse,
  });
  google.accounts.id.renderButton(document.getElementById("googleSignInBtn"), {
    theme: "outline",
    size: "large",
    width: "100%",
  });
  google.accounts.id.prompt();
};

setInterval(() => {
  if (document.getElementById("time_now").value)
    document.getElementById("time_now").value = getBDTime();
}, 60000);

// Employee info
async function loadEmployeeInfo(email) {
  try {
    const res = await fetch(apiBase + "/config/employees");
    const data = await res.json();
    const emp = data.find((e) => e.email.toLowerCase() === email.toLowerCase());
    if (emp) {
      document.getElementById("emp_id").value = emp.id;
      document.getElementById("office_email").value = emp.office_email;
      document.getElementById("full_name").value = emp.full_name;
      document.getElementById("nickname").value = emp.nickname;
    } else {
      showToast("Email not registered", false);
    }
  } catch (err) {
    console.warn(err);
  }
}

// Task block template
async function createTaskBlock() {
  const res = await fetch(apiBase + "/config/companies");
  const data = await res.json();
  const container = document.getElementById("tasks_container");

  const taskDiv = document.createElement("div");
  taskDiv.className = "task-block";

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "remove-task";
  removeBtn.innerText = "×";
  removeBtn.onclick = () => taskDiv.remove();
  taskDiv.appendChild(removeBtn);

  // Task For
  const taskForLabel = document.createElement("label");
  taskForLabel.innerText = "Task For";
  taskDiv.appendChild(taskForLabel);

  const taskForSel = document.createElement("select");
  taskForSel.innerHTML = `<option value="">-- select --</option>`;
  data.companies.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.text = c;
    taskForSel.appendChild(opt);
  });
  const otherOpt = document.createElement("option");
  otherOpt.value = "Other";
  otherOpt.text = "Other";
  taskForSel.appendChild(otherOpt);
  taskDiv.appendChild(taskForSel);

  const taskForOther = document.createElement("input");
  taskForOther.type = "text";
  taskForOther.placeholder = "Enter task for";
  taskForOther.style.display = "none";
  taskForOther.style.marginTop = "5px";
  taskDiv.appendChild(taskForOther);

  taskForSel.addEventListener("change", () => {
    taskForOther.style.display =
      taskForSel.value === "Other" ? "block" : "none";
  });

  // Task Name
  const taskNameLabel = document.createElement("label");
  taskNameLabel.innerText = "Task Name *";
  taskDiv.appendChild(taskNameLabel);
  const taskNameInput = document.createElement("input");
  taskNameInput.type = "text";
  taskNameInput.placeholder = "Enter task name";
  taskDiv.appendChild(taskNameInput);

  // Task Details
  const taskDetailsLabel = document.createElement("label");
  taskDetailsLabel.innerText = "Task Details *";
  taskDiv.appendChild(taskDetailsLabel);
  const taskDetailsInput = document.createElement("textarea");
  taskDetailsInput.rows = 3;
  taskDetailsInput.placeholder = "Enter task details";
  taskDiv.appendChild(taskDetailsInput);

  // My Role
  const myRoleLabel = document.createElement("label");
  myRoleLabel.innerText = "My Role to Complete Task *";
  taskDiv.appendChild(myRoleLabel);
  const myRoleInput = document.createElement("textarea");
  myRoleInput.rows = 2;
  myRoleInput.placeholder = "Enter your role";
  taskDiv.appendChild(myRoleInput);

  container.appendChild(taskDiv);
}

// Add first task initially
document
  .getElementById("addTaskBtn")
  .addEventListener("click", createTaskBlock);

// Show/hide checkout fields
document.getElementById("action").addEventListener("change", (e) => {
  if (e.target.value === "checkout") {
    document.getElementById("checkoutFields").classList.remove("hidden");
    if (document.getElementById("tasks_container").children.length === 0) {
      createTaskBlock();
    }
  } else {
    document.getElementById("checkoutFields").classList.add("hidden");
    document.getElementById("tasks_container").innerHTML = "";
  }
});

// Submit with modern spinner and mandatory validation
document.getElementById("attForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const submitBtn = e.target.querySelector("button[type='submit']");
  submitBtn.disabled = true;
  const originalText = submitBtn.innerText;
  submitBtn.innerHTML = 'Submitting <span class="spinner"></span>';

  const action = document.getElementById("action").value.trim();
  const payload = { email: userEmail, action };

  if (action === "checkout") {
    const taskBlocks = document.querySelectorAll(".task-block");
    if (taskBlocks.length === 0) {
      showToast("Please add at least one task", false);
      submitBtn.disabled = false;
      submitBtn.innerText = originalText;
      return;
    }
    const tasks = [];
    for (const block of taskBlocks) {
      let task_for = block.querySelector("select").value.trim();
      if (task_for === "Other")
        task_for = block.querySelector("input").value.trim();
      const task_name = block
        .querySelectorAll("input,textarea")[1]
        .value.trim();
      const task_details = block
        .querySelectorAll("input,textarea")[2]
        .value.trim();
      const my_role = block.querySelectorAll("input,textarea")[3].value.trim();

      if (!task_for || !task_name || !task_details || !my_role) {
        showToast("All fields (*) are mandatory for each task", false);
        submitBtn.disabled = false;
        submitBtn.innerText = originalText;
        return;
      }
      tasks.push({ task_for, task_name, task_details, my_role });
    }
    payload.tasks = tasks;
  }

  try {
    const res = await fetch(apiBase + "/attendance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast("Error: " + (data.detail || JSON.stringify(data)), false);
      submitBtn.disabled = false;
      submitBtn.innerText = originalText;
      return;
    }
    showToast("Attendance submitted successfully!");
    document.getElementById("attForm").reset();
    document.getElementById("attForm").classList.add("hidden");
    document.getElementById("checkoutFields").classList.add("hidden");
    document.getElementById("tasks_container").innerHTML = "";
    document.getElementById("googleSignInBtn").style.display = "block";
    userEmail = "";
  } catch (err) {
    showToast("Error: " + err.message, false);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerText = originalText;
  }
});
