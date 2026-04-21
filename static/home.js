const menuToggle = document.getElementById("menuToggle");
const mobileNav = document.getElementById("mobileNav");

if (menuToggle && mobileNav) {
    menuToggle.addEventListener("click", () => {
        mobileNav.classList.toggle("open");
    });

    mobileNav.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            mobileNav.classList.remove("open");
        });
    });
}
