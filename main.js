// /OLIVIA_WEB/olivia_app/static/js/main.js

import { initNavbar } from './ui/navbar.js';
import { initGestionPerfil } from './modules/gestionPerfil.js';
import { initGestionUsuarios } from './modules/gestionUsuarios.js';
import { initVistaPronosticos } from './modules/vistaPronosticos.js';
import { initVistaDashboard } from './modules/vistaDashboard.js';

/**
 * Función principal que se ejecuta cuando el dashboard (home.html) se carga.
 */
document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Inicializar UI y Perfil
    initNavbar();
    initGestionPerfil(); 

    // 2. Asignar los "listeners" a los enlaces de la barra lateral (sidebar)
    const mainContent = document.getElementById('main-content');
    const logoUrl = document.body.getAttribute('data-logo-url') || '';

    // Mapa de vistas para limpiar el código
    const vistas = {
        'home-link': () => {
            mainContent.innerHTML = `
                <div class="home-container">
                    <div class="home-text">
                        <h1>Bienvenido a <br> <span class="highlight">Olivia</span></h1>
                        <p>OLIVIA es un software que permite predecir las ventas, facilitando la planificación de compras.</p>
                    </div>
                    <div class="home-image">
                        <img src="${logoUrl}" alt="Logo del Sistema">
                    </div>
                </div>
            `;
        },
        'reportes-link': () => initVistaPronosticos(mainContent),
        'dashboard-link': () => initVistaDashboard(mainContent),
        'add-user': () => initGestionUsuarios(mainContent)
    };

    // Asignar listeners a todos los enlaces del sidebar
    document.querySelectorAll('.sidebar nav ul li a').forEach(link => {
        if (vistas[link.id]) {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                vistas[link.id](); // Llama a la función de la vista
                setActiveLink(e.currentTarget);
            });
        }
    });

    // Función para resaltar el enlace activo
    function setActiveLink(linkElement) {
        document.querySelectorAll('.sidebar nav ul li a.active').forEach(link => {
            link.classList.remove('active');
        });
        linkElement.classList.add('active');
    }

    // Cargar la vista "Inicio" por defecto
    document.getElementById('home-link')?.click();
});