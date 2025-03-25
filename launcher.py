import sys
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import subprocess
import pygame
import minecraft_launcher_lib
import requests
import urllib.parse
import threading
import logging
import webbrowser
import platform

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def resource_path(relative_path: str) -> str:
    """Obtiene la ruta absoluta al recurso, tanto en desarrollo como en modo frozen."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# URLs fijas de mods
SODIUM_URL = "https://cdn.modrinth.com/data/AANobbMI/versions/FRXt5xaI/sodium-fabric-0.6.10%2Bmc1.21.4.jar"
LITHIUM_URL = "https://cdn.modrinth.com/data/gvQqBUqZ/versions/kLc5Oxr4/lithium-fabric-0.14.8%2Bmc1.21.4.jar"
SKIN_OVERRIDES_URL = "https://cdn.modrinth.com/data/GON0Fdk5/versions/MU0u3ea4/skin_overrides-2.2.3%2B1.21.4.jar"
FABRIC_API_URL = "https://cdn.modrinth.com/data/P7dR8mSH/versions/ZNwYCTsk/fabric-api-0.118.0%2B1.21.4.jar"

class ResizableWindow:
    def __init__(self) -> None:
        self.window = tk.Tk()
        self.original_width = 800
        self.original_height = 600

        # Variables para optimización de redimensionamiento
        self._resize_id = None
        self._last_resize_time = 0
        self._resize_delay = 150
        self._max_cache_size = 5

        # Diccionario para almacenar las versiones Fabric instaladas:
        # {vanilla_version: fabric_version_id}
        self.fabric_versions: dict[str, str] = {}

        # Determinar la carpeta base donde se encuentra el script o ejecutable
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        # La carpeta "MNC_KA Client" se creará junto al archivo .py o .exe
        self.minecraft_dir = os.path.join(base_path, "MNC_KA Client")
        self.create_minecraft_folders()
        self.preguntar_version()  # Pregunta la versión vanilla si aún no se ha instalado

        # Se elimina la inicialización temprana de pygame para evitar problemas en el proceso de congelado
        # pygame.mixer.init()

        # Centrar ventana
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - self.original_width) // 2
        y = (screen_height - self.original_height) // 2
        self.window.geometry(f"{self.original_width}x{self.original_height}+{x}+{y}")

        # Configuración de botones en el menú principal
        self.button_configs = [
            ("1.png", 0.71, 0.38, 0.29, 0.62, self.iniciar_minecraft),
            ("2.png", 0.00, 0.38, 0.70, 0.15, self.mostrar_versiones),
            ("3.png", 0.00, 0.01, 0.25, 0.36, self.abrir_juego),
            ("4.png", 0.26, 0.01, 0.74, 0.14, self.abrir_canal),
            ("5.png", 0.26, 0.17, 0.74, 0.20, self.reproducir_musica),
            ("6.png", 0.00, 0.54, 0.70, 0.46, self.configurar_usuario)
        ]
        self.buttons = []
        self.images_cache: dict[tuple, list] = {}
        self.create_buttons()

        self.window.bind('<Configure>', self._handle_resize)

        # Variables de configuración de usuario
        self.username: str = ""
        self.ram: int = 0
        self.selected_version: str = ""

    def create_minecraft_folders(self) -> None:
        """Crea las carpetas necesarias para el cliente Minecraft."""
        folders = [
            self.minecraft_dir,
            os.path.join(self.minecraft_dir, "assets"),
            os.path.join(self.minecraft_dir, "songs"),
            os.path.join(self.minecraft_dir, "libraries"),
            os.path.join(self.minecraft_dir, "runtime"),
            os.path.join(self.minecraft_dir, "mods")  # Para los mods
        ]
        for folder in folders:
            if not os.path.exists(folder):
                os.makedirs(folder)
                logging.info(f"Carpeta creada: {folder}")

    def _handle_resize(self, event: tk.Event) -> None:
        if event.widget != self.window:
            return
        current_time = time.time() * 1000
        if self._resize_id:
            self.window.after_cancel(self._resize_id)
        if current_time - self._last_resize_time > self._resize_delay:
            self.create_buttons()
            self._last_resize_time = current_time
        else:
            self._resize_id = self.window.after(self._resize_delay, self.create_buttons)

    def _cleanup_cache(self) -> None:
        if len(self.images_cache) > self._max_cache_size:
            for key in sorted(self.images_cache.keys())[:-self._max_cache_size]:
                del self.images_cache[key]

    def create_buttons(self) -> None:
        """Crea y posiciona los botones en la ventana según la configuración."""
        for button in self.buttons:
            button.destroy()
        self.buttons.clear()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        cache_key = (width, height)
        if cache_key in self.images_cache:
            cached_buttons = self.images_cache[cache_key]
            for (x, y, w, h, command), photo in cached_buttons:
                button = tk.Button(self.window, image=photo, command=command,
                                   borderwidth=0, highlightthickness=0)
                button.image = photo
                button.place(x=x, y=y, width=w, height=h)
                self.buttons.append(button)
            return
        cached_buttons = []
        for img_file, rx, ry, rw, rh, command in self.button_configs:
            try:
                x = int(rx * width)
                y = int(ry * height)
                w1 = int(rw * width)
                h1 = int(rh * height)
                img_path = resource_path(os.path.join("assets", img_file))
                img = Image.open(img_path)
                img = img.resize((w1, h1), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                button = tk.Button(self.window, image=photo, command=command,
                                   borderwidth=0, highlightthickness=0)
                button.image = photo
                button.place(x=x, y=y, width=w1, height=h1)
                cached_buttons.append(((x, y, w1, h1, command), photo))
                self.buttons.append(button)
            except Exception as e:
                logging.error(f"Error al crear botón {img_file}: {e}")
        self.images_cache[cache_key] = cached_buttons
        self._cleanup_cache()

    def preguntar_version(self) -> None:
        """Pregunta la versión vanilla de Minecraft a instalar si aún no se ha instalado."""
        win = tk.Toplevel(self.window)
        win.title("Instalar Versión")
        win.geometry("300x150")
        win.transient(self.window)
        win.grab_set()
        tk.Label(win, text="Ingresa la versión de Minecraft\n(ej: 1.21.4):").pack(pady=10)
        entry = tk.Entry(win)
        entry.pack(pady=5)

        def instalar_ver() -> None:
            ver = entry.get().strip()
            if not ver:
                messagebox.showerror("Error", "Debe ingresar una versión válida.")
                return

            def install_task() -> None:
                try:
                    messagebox.showinfo("Info", f"Instalando Minecraft {ver}...\nPuede tardar varios minutos.")
                    minecraft_launcher_lib.install.install_minecraft_version(ver, self.minecraft_dir)
                    self.window.after(0, lambda: messagebox.showinfo("Éxito", f"Minecraft {ver} instalado correctamente"))
                except Exception as e:
                    logging.exception("Error al instalar la versión de Minecraft.")
                    self.window.after(0, lambda: messagebox.showerror("Error", f"No se pudo instalar {ver}: {e}"))
                finally:
                    self.window.after(0, win.destroy)

            threading.Thread(target=install_task, daemon=True).start()

        tk.Button(win, text="Instalar", command=instalar_ver).pack(pady=10)

    def instalar_fabric_prompt(self) -> None:
        """
        Instala Fabric para una versión vanilla, descarga obligatoriamente Fabric API,
        y luego pregunta por mods adicionales.
        """
        win = tk.Toplevel(self.window)
        win.title("Instalar Fabric")
        win.geometry("300x150")
        win.transient(self.window)
        win.grab_set()
        tk.Label(win, text="¿De qué versión instalar Fabric?\n(ej: 1.21.4):").pack(pady=10)
        entry = tk.Entry(win)
        entry.pack(pady=5)

        def instalar() -> None:
            ver = entry.get().strip()
            if not ver:
                messagebox.showerror("Error", "Debes ingresar una versión")
                return

            def fabric_install_task() -> None:
                try:
                    default_fab = "0.16.10"  # Versión actualizada de Fabric
                    self.window.after(0, lambda: messagebox.showinfo("Info", f"Instalando Fabric {default_fab} para Minecraft {ver}...\nPuede tardar."))
                    minecraft_launcher_lib.fabric.install_fabric(ver, self.minecraft_dir, default_fab)
                    fab_id = f"fabric-loader-{default_fab}-{ver}"
                    self.fabric_versions[ver] = fab_id
                    self.window.after(0, lambda: messagebox.showinfo("Éxito", f"Fabric {default_fab} instalado para Minecraft {ver}."))
                    # Instalar Fabric API obligatoriamente
                    self.download_mod_direct("FabricAPI", FABRIC_API_URL)
                    # Preguntar por mods adicionales
                    self.post_fabric_install_prompt(ver)
                except Exception as e:
                    logging.exception("Error al instalar Fabric.")
                    self.window.after(0, lambda: messagebox.showerror("Error", f"No se pudo instalar Fabric: {e}"))
                finally:
                    self.window.after(0, win.destroy)

            threading.Thread(target=fabric_install_task, daemon=True).start()

        tk.Button(win, text="Instalar Fabric", command=instalar).pack(pady=10)

    def post_fabric_install_prompt(self, vanilla_ver: str) -> None:
        """
        Después de instalar Fabric (y Fabric API), pregunta si se desean instalar mods adicionales.
        Se guarda un registro en un archivo para no repetir la acción para esa versión.
        """
        mod_record = os.path.join(self.minecraft_dir, "mods", f"mods_installed_{vanilla_ver}.txt")
        if os.path.exists(mod_record):
            return
        if messagebox.askyesno("Instalar mod de skin", "¿Quieres instalar el mod de skin (SkinOverrides)?"):
            self.download_mod_direct("SkinOverrides", SKIN_OVERRIDES_URL)
        if messagebox.askyesno("Instalar mods de optimización", "¿Quieres instalar los mods de optimización (Sodium y Lithium)?"):
            self.download_mod_direct("Sodium", SODIUM_URL)
            self.download_mod_direct("Lithium", LITHIUM_URL)
        with open(mod_record, "w") as f:
            f.write("mods_installed")

    def download_mod_direct(self, mod_name: str, url: str) -> None:
        """
        Descarga el mod desde la URL real y lo guarda en la carpeta 'mods'.
        Se muestra una ventana con barra de progreso.
        Además, si el mod a descargar no es FabricAPI, se verifica si ya está presente FabricAPI;
        de lo contrario, se pregunta al usuario si desea descargarlo.
        """
        mods_folder = os.path.join(self.minecraft_dir, "mods")
        if not os.path.exists(mods_folder):
            os.makedirs(mods_folder)
        if mod_name.lower() != "fabricapi":
            fabricapi_found = any("fabric-api" in f.lower() for f in os.listdir(mods_folder))
            if not fabricapi_found:
                if messagebox.askyesno("Fabric API requerido", f"El mod {mod_name} requiere Fabric API. ¿Deseas descargarlo?"):
                    self.download_mod_direct("FabricAPI", FABRIC_API_URL)
        filename = urllib.parse.unquote(os.path.basename(url))
        filepath = os.path.join(mods_folder, filename)

        # Crear ventana de progreso
        progress_win = tk.Toplevel(self.window)
        progress_win.title(f"Descargando {mod_name}")
        progress_win.geometry("350x100")
        progress_win.transient(self.window)
        progress_win.grab_set()
        tk.Label(progress_win, text=f"Descargando {mod_name}...").pack(pady=(10, 0))
        progressbar = ttk.Progressbar(progress_win, orient="horizontal", length=300, mode="determinate")
        progressbar.pack(pady=10)
        percent_label = tk.Label(progress_win, text="0%")
        percent_label.pack()

        # Variable compartida para actualizar el progreso (se usa un diccionario para evitar problemas con el scope)
        progress_data = {"progress": 0}

        def update_progress() -> None:
            progressbar["value"] = progress_data["progress"]
            percent_label.config(text=f"{progress_data['progress']:.0f}%")
            if progress_data["progress"] < 100:
                progress_win.after(100, update_progress)
            else:
                progress_win.destroy()

        update_progress()  # Inicia la actualización periódica de la barra

        def download_task() -> None:
            try:
                r = requests.get(url, stream=True)
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                if total_length is None:
                    total_length = 0
                else:
                    total_length = int(total_length)
                downloaded = 0
                with open(filepath, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            if total_length:
                                downloaded += len(chunk)
                                progress_data["progress"] = min((downloaded / total_length) * 100, 100)
                # Forzar 100% al finalizar
                progress_data["progress"] = 100
                self.window.after(0, lambda: messagebox.showinfo("Mod descargado", f"{mod_name} descargado y guardado en mods."))
            except Exception as e:
                logging.exception("Error en la descarga del mod.")
                self.window.after(0, lambda: messagebox.showerror("Error", f"No se pudo descargar {mod_name}: {e}"))
                progress_data["progress"] = 100  # Cerrar la ventana en caso de error

        threading.Thread(target=download_task, daemon=True).start()

    def abrir_carpeta_versiones(self) -> None:
        """Abre la carpeta donde se guardan las versiones de Minecraft."""
        versions_path = os.path.join(self.minecraft_dir, "versions")
        try:
            if platform.system() == "Windows":
                os.startfile(versions_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", versions_path])
            else:  # Linux y otros
                subprocess.run(["xdg-open", versions_path])
        except Exception as e:
            logging.exception("Error al abrir la carpeta de versiones.")
            messagebox.showerror("Error", f"No se pudo abrir la carpeta de versiones: {e}")

    def mostrar_versiones(self) -> None:
        """
        Muestra las versiones instaladas para seleccionar
        la versión a iniciar. Permite activar Fabric mediante un Checkbutton y añade un botón
        para abrir la carpeta de versiones.
        """
        versions = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_dir)
        if not versions:
            messagebox.showinfo("Info", "No hay versiones instaladas")
            return
        win = tk.Toplevel(self.window)
        win.title("Seleccionar Versión")
        tk.Label(win, text="Elige una versión:").pack(pady=10)
        for ver in versions:
            ver_id = ver['id']
            if "fabric-loader" in ver_id:
                continue
            frame = tk.Frame(win)
            frame.pack(fill="x", padx=10, pady=5)
            tk.Label(frame, text=ver_id).pack(side="left")
            usar_fab = tk.BooleanVar(value=False)
            text_cb = "Activar Fabric" if ver_id in self.fabric_versions else "Instalar Fabric"
            cb = tk.Checkbutton(frame, text=text_cb, variable=usar_fab)
            cb.pack(side="left", padx=10)

            def on_toggle(v=ver_id, var=usar_fab, widget=cb):
                if var.get() and (v not in self.fabric_versions):
                    if messagebox.askyesno("Instalar Fabric", f"Fabric no instalado para {v}. ¿Instalarlo?"):
                        def install_fabric_task() -> None:
                            try:
                                default_fab = "0.16.10"
                                self.window.after(0, lambda: messagebox.showinfo("Info", f"Instalando Fabric {default_fab} para {v}..."))
                                minecraft_launcher_lib.fabric.install_fabric(v, self.minecraft_dir, default_fab)
                                fab_id = f"fabric-loader-{default_fab}-{v}"
                                self.fabric_versions[v] = fab_id
                                self.window.after(0, lambda: widget.config(text="Activar Fabric"))
                            except Exception as e:
                                logging.exception("Error al instalar Fabric en la versión seleccionada.")
                                self.window.after(0, lambda: messagebox.showerror("Error", f"No se pudo instalar Fabric: {e}"))
                                var.set(False)
                        threading.Thread(target=install_fabric_task, daemon=True).start()
                    else:
                        var.set(False)
            cb.config(command=on_toggle)

            def on_select(v=ver_id, var=usar_fab):
                if var.get() and (v in self.fabric_versions):
                    self.selected_version = self.fabric_versions[v]
                    mod_record = os.path.join(self.minecraft_dir, "mods", f"mods_installed_{v}.txt")
                    if not os.path.exists(mod_record):
                        self.post_fabric_install_prompt(v)
                    messagebox.showinfo("Info", f"Se ha activado Fabric para {v}.")
                else:
                    self.selected_version = v
                    messagebox.showinfo("Info", f"Se ha seleccionado {v} sin Fabric.")
                win.destroy()
            tk.Button(frame, text="Seleccionar", command=on_select).pack(side="right")
        tk.Button(win, text="Abrir carpeta de versiones", command=self.abrir_carpeta_versiones).pack(pady=10)

    def iniciar_minecraft(self) -> None:
        """Inicia Minecraft usando la versión seleccionada (vanilla o con Fabric)."""
        if not (self.username and self.ram):
            messagebox.showerror("Error", "Configura usuario y RAM primero")
            return
        if not self.selected_version:
            messagebox.showerror("Error", "Selecciona una versión primero")
            return
        options = {
            'username': self.username,
            'uuid': '',
            'token': '',
            'jvmArguments': [f"-Xmx{self.ram}G", f"-Xms{self.ram}G"],
            'launcherVersion': "1.0.0"
        }
        if self.selected_version.startswith("fabric-loader-"):
            version_dir = os.path.join(self.minecraft_dir, "versions", self.selected_version)
            jar_filename = self.selected_version + ".jar"
            jar_path = os.path.join(version_dir, jar_filename)
            if not os.path.exists(jar_path):
                messagebox.showerror("Error", f"No se encontró {jar_filename} en {version_dir}")
                return
        try:
            cmd = minecraft_launcher_lib.command.get_minecraft_command(self.selected_version, self.minecraft_dir, options)
            threading.Thread(target=lambda: subprocess.run(cmd), daemon=True).start()
        except Exception as e:
            logging.exception("Error al iniciar Minecraft.")
            messagebox.showerror("Error", f"Error al iniciar Minecraft: {e}")

    def abrir_juego(self) -> None:
        """Abre la URL del juego en el navegador."""
        webbrowser.open("https://oscarito1600.github.io/oscarito16003.github.io/Juego.html")

    def abrir_canal(self) -> None:
        """Abre la URL del canal en el navegador."""
        webbrowser.open("https://www.youtube.com/@MinecraftKA")

    def reproducir_musica(self) -> None:
        """Reproduce la primera canción disponible en la carpeta 'songs'."""
        # Inicializa pygame.mixer si aún no está inicializado
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        songs_folder = os.path.join(self.minecraft_dir, "songs")
        try:
            files = [f for f in os.listdir(songs_folder) if f.endswith(".mp3")]
        except Exception as e:
            logging.exception("Error al acceder a la carpeta de canciones.")
            messagebox.showerror("Error", "No se pudo acceder a la carpeta 'songs'")
            return
        if files:
            try:
                pygame.mixer.music.load(os.path.join(songs_folder, files[0]))
                pygame.mixer.music.play()
            except Exception as e:
                logging.exception("Error al reproducir la música.")
                messagebox.showerror("Error", "Error al reproducir la canción")
        else:
            messagebox.showerror("Error", "No hay canciones en la carpeta 'songs'")

    def configurar_usuario(self) -> None:
        """Configura el usuario y la RAM a usar."""
        win = tk.Toplevel(self.window)
        win.title("Configuración")
        win.geometry("300x200")
        tk.Label(win, text="Usuario:").pack(pady=5)
        user_entry = tk.Entry(win)
        user_entry.pack(pady=5)
        tk.Label(win, text="RAM (GB):").pack(pady=5)
        ram_entry = tk.Entry(win)
        ram_entry.pack(pady=5)

        def guardar() -> None:
            username = user_entry.get().strip()
            ram_str = ram_entry.get().strip()
            if not username or not ram_str:
                messagebox.showerror("Error", "Debes llenar todos los campos")
                return
            try:
                ram_value = int(ram_str)
                self.username = username
                self.ram = ram_value
                win.destroy()
                messagebox.showinfo("Info", "Configuración guardada")
            except ValueError:
                messagebox.showerror("Error", "La RAM debe ser un número entero")

        tk.Button(win, text="Guardar", command=guardar).pack(pady=10)

    def run(self) -> None:
        self.window.mainloop()

if __name__ == "__main__":
    app = ResizableWindow()
    app.run()
