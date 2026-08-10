"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("bg3dContainer");
  if (!container) {
    return;
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reducedMotion.matches) {
    return;
  }

  let frameId = null;
  let mouseX = 0;
  let mouseY = 0;

  const updateBackground = () => {
    const x = (mouseX / window.innerWidth - 0.5) * 2;
    const y = (mouseY / window.innerHeight - 0.5) * 2;
    const rotateY = x * 2;
    const rotateX = y * -2;

    container.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    frameId = null;
  };

  document.addEventListener(
    "mousemove",
    (event) => {
      mouseX = event.clientX;
      mouseY = event.clientY;
      if (frameId === null) {
        frameId = window.requestAnimationFrame(updateBackground);
      }
    },
    { passive: true },
  );

  document.documentElement.addEventListener("mouseleave", () => {
    container.style.transform = "rotateX(0deg) rotateY(0deg)";
  });
});
