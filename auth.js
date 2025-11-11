// /OLIVIA_WEB/olivia_app/static/js/auth.js

document.addEventListener("DOMContentLoaded", function () {
    const emailInput = document.getElementById("login-usuario");
    const passwordInput = document.getElementById("login-password");
    const loginButton = document.getElementById("login-button");
    const mensajeError = document.getElementById("mensaje-error");
    const toggleIcon = document.querySelector(".toggle-password");

    function validarFormulario() {
        if (!emailInput || !passwordInput || !loginButton) return;
        
        let email = emailInput.value.trim();
        let password = passwordInput.value.trim();
        let emailRegex = /^[^\s@]+@[^\s@]+\.[cC][oO][mM]+$/; // Simple regex
        let emailValido = emailRegex.test(email);
        let passwordValida = password.length > 6;

        if (emailValido && passwordValida) {
            loginButton.disabled = false;
            loginButton.classList.add("enabled");
        } else {
            loginButton.disabled = true;
            loginButton.classList.remove("enabled");
        }
    }

    if (emailInput) emailInput.addEventListener("input", validarFormulario);
    if (passwordInput) passwordInput.addEventListener("input", validarFormulario);

    // Asignar funciones al objeto global 'window' para que 'onclick' funcione
    window.togglePassword = function() {
        if (passwordInput.type === "password") {
            passwordInput.type = "text";
            toggleIcon.classList.remove("fa-eye");
            toggleIcon.classList.add("fa-eye-slash");
        } else {
            passwordInput.type = "password";
            toggleIcon.classList.remove("fa-eye-slash");
            toggleIcon.classList.add("fa-eye");
        }
    };

    window.login = function() {
        let usuario = emailInput.value;
        let password = passwordInput.value;

        if (usuario.trim() === "" || password.trim() === "") {
            mensajeError.textContent = "⚠️ Por favor, completa todos los campos.";
            mensajeError.style.display = "block";
            return;
        }

        // Llama a la ruta /login en el Blueprint 'auth'
        fetch("/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ correo: usuario, contraseña: password })
        })
        .then(response => response.json())
        .then(data => {
            if (data.mensaje === "Login exitoso") {
                window.location.href = "/home"; // Redirige al dashboard
            } else {
                mensajeError.textContent = "⚠️ " + (data.mensaje || "Correo o contraseña incorrectos.");
                mensajeError.style.display = "block";
            }
        })
        .catch(error => {
            console.error("Error:", error);
            mensajeError.textContent = "⚠️ Error en el servidor. Intente más tarde.";
            mensajeError.style.display = "block";
        });
    };

    // Validar el formulario al cargar la página (para campos pre-rellenados)
    validarFormulario();
});