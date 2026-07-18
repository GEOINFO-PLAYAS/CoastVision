# FES2014 externo

Los 34 NetCDF de FES2014b pesan aproximadamente 4,5 GB y **no deben entrar en
Git ni en los ZIP de versiones**. Defina `TIDE_MODEL_DIR` apuntando a una raíz
con esta estructura:

```text
tide_models/
└─ fes2014/
   └─ ocean_tide/
      ├─ m2.nc
      ├─ s2.nc
      └─ ... 34 constituyentes
```

Valide la instalación con:

```powershell
python scripts/09_validate_fes2014.py
```

No copie `descargar_fes.py` de la versión del compañero: contenía una
credencial incrustada. Esa credencial debe rotarse en AVISO+.

