document.querySelectorAll(".alert").forEach((alertNode) => {
    window.setTimeout(() => {
        const alert = bootstrap.Alert.getOrCreateInstance(alertNode);
        alert.close();
    }, 4000);
});
