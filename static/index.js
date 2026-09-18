var socketio = io();

const safeColor = (color) => {
    if (!Array.isArray(color) || color.length !== 3) return "rgb(255,255,255)";

    const channels = color.map((value) => {
        const number = Number(value);
        if (!Number.isFinite(number)) return 255;
        return Math.max(0, Math.min(255, Math.round(number)));
    });

    return `rgb(${channels.join(",")})`;
};

const appendMessage = (name, msg, color = [255, 255, 255], messageColor = null) => {
    const wrapper = document.createElement("div");
    wrapper.className = "text";

    const fullMessage = document.createElement("span");
    fullMessage.className = "msg-full";

    const nameElement = document.createElement("strong");
    nameElement.className = "msg-name";
    nameElement.style.color = safeColor(color);
    nameElement.textContent = `${String(name ?? "")} `;

    fullMessage.appendChild(nameElement);

    if (messageColor) {
        const messageElement = document.createElement("strong");
        messageElement.style.color = messageColor;
        messageElement.textContent = String(msg ?? "");
        fullMessage.appendChild(messageElement);
    } else {
        fullMessage.appendChild(document.createTextNode(String(msg ?? "")));
    }

    wrapper.appendChild(fullMessage);
    messages.appendChild(wrapper);
};

const createJoinMessage = (name, msg, color) => {
    appendMessage(name, msg, color, "#b7ffb0");
};

const createMessage = (name, msg, color) => {
    appendMessage(name, msg, color);
};

const createLeaveMessage = (name, msg, color) => {
    appendMessage(name, msg, color, "#ff7676");
};

socketio.on("message", (data) => {
    if (!data || typeof data !== "object") return;

    if (data.message === "has joined the lobby") {
        createJoinMessage(data.name, data.message, data.color);
    } else if (data.message === "has left the lobby") {
        createLeaveMessage(data.name, data.message, data.color);
    } else {
        createMessage(data.name, data.message, data.color);
    }
});

const sendMessage = () => {
    const message = document.getElementById("message");
    if (!message) return;

    const value = message.value.trim();
    if (!value) return;

    socketio.emit("message", { data: value.slice(0, 300) });
    message.value = "";
};

const msgForm = document.getElementById("content");
if (msgForm) {
    msgForm.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            sendMessage();
        }
    });
}

const sendButton = document.getElementById("send-btn");
if (sendButton) {
    sendButton.addEventListener("click", sendMessage);
}
