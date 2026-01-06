// CONFIGURATION SUPABASE (Front-end)
const supabaseUrl = "https://lgkppbnfxqpmmszphztz.supabase.co";
const supabaseKey = "TON_ANON_KEY"; // Remplace par ta clé anonyme Supabase

// Gestion réelle de l'upload d'image
async function uploadProfileImage(input) {
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    const fileExt = file.name.split('.').pop();
    const fileName = `${Math.random()}.${fileExt}`;
    const filePath = `avatars/${fileName}`;

    try {
        // 1. Upload vers le Bucket Supabase
        const { data, error } = await supabase.storage
            .from('user_assets')
            .upload(filePath, file);

        if (error) throw error;

        // 2. Récupérer l'URL publique
        const { data: urlData } = supabase.storage
            .from('user_assets')
            .getPublicUrl(filePath);

        const publicUrl = urlData.publicUrl;

        // 3. Mettre à jour l'affichage
        document.getElementById('profileDisplay').src = publicUrl;

        // 4. Envoyer à Flask pour enregistrer en base de données
        fetch('/update_profile_avatar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ avatar_url: publicUrl })
        });

        alert("Photo de profil mise à jour ! ✨");

    } catch (error) {
        console.error("Erreur d'upload:", error);
        alert("Erreur lors de l'upload de l'image.");
    }
}

// Moteur de recherche (Ton code corrigé)
function searchProduct() {
    const val = document.getElementById('searchInput').value;
    if (val.trim().length > 0) {
        window.location.href = '/?search=' + encodeURIComponent(val);
    }
}

// Changement de Thème (Ton code)
function toggleTheme() {
    document.body.classList.toggle('light-mode');
    const isLight = document.body.classList.contains('light-mode');
    localStorage.setItem('aura_theme', isLight ? 'light' : 'dark');
}

document.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('aura_theme') === 'light') {
        document.body.classList.add('light-mode');
    }
});
