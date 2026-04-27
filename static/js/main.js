// ─── BURGER MENU ───
document.addEventListener('DOMContentLoaded', function () {
    const burger = document.getElementById('navBurger');
    const links  = document.getElementById('navLinks');

    if (!burger || !links) return;

    burger.addEventListener('click', function () {
        links.classList.toggle('open');
    });

    // Fermer au clic sur un lien
    links.querySelectorAll('a').forEach(a => {
        a.addEventListener('click', () => {
            links.classList.remove('open');
        });
    });
});