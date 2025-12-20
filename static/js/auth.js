const regionsData = {
    "Guinée": ["Conakry", "Labé"],
    "Sénégal": ["Dakar", "Thiès", "Saint-Louis"]
};

function loadRegions() {
    const country = document.getElementById('country').value;
    const regionSelect = document.getElementById('region');
    regionSelect.innerHTML = '<option value="">Sélectionnez votre région</option>';
    
    if (country && regionsData[country]) {
        regionsData[country].forEach(r => {
            let opt = document.createElement('option');
            opt.value = r;
            opt.innerHTML = r;
            regionSelect.appendChild(opt);
        });
    }
}

async function handleRegister(e) {
    e.preventDefault();
    // 1. Vérification des mots de passe
    if(password !== confirm_password) return alert("Mots de passe différents");

    // 2. Inscription Supabase
    const { data, error } = await supabase.auth.signUp({
        email: email,
        password: password,
        options: {
            data: { // Ces données iront dans le profil via le Trigger SQL
                first_name: prenom,
                last_name: nom,
                phone: phone,
                country: country,
                region: region
            }
        }
    });
    
    if(!error) alert("Vérifiez votre boîte mail pour activer Aura !");
}
