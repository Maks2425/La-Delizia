const ABOUT_FLASH_DURATION_MS = 2000;

function initMobileMenu() {
    const menuToggle = document.getElementById("menuToggle");
    const mobileNav = document.getElementById("mobileNav");

    if (!menuToggle || !mobileNav) {
        return;
    }

    menuToggle.addEventListener("click", () => {
        mobileNav.classList.toggle("open");
    });

    mobileNav.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            mobileNav.classList.remove("open");
        });
    });
}

function initAboutHighlight() {
    const aboutSection = document.getElementById("about");
    const aboutLinks = document.querySelectorAll('a[href="#about"]');

    if (!aboutSection || aboutLinks.length === 0) {
        return;
    }

    aboutLinks.forEach((link) => {
        link.addEventListener("click", () => {
            aboutSection.classList.remove("about-flash");
            // Force reflow so animation can restart on repeated clicks.
            void aboutSection.offsetWidth;
            aboutSection.classList.add("about-flash");

            setTimeout(() => {
                aboutSection.classList.remove("about-flash");
            }, ABOUT_FLASH_DURATION_MS);
        });
    });
}

initMobileMenu();
initAboutHighlight();
