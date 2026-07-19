from __future__ import annotations

import os
import pickle
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    Credentials = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    InstalledAppFlow = None  # type: ignore[assignment]
    build = None  # type: ignore[assignment]
    MediaFileUpload = None  # type: ignore[assignment]


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
DEFAULT_TOKEN_FILE = "token_youtube_upload.json"
DEFAULT_CLIENT_SECRET_FILES = ("client_secret.json", "client_secrets.json")
DEFAULT_TOKEN_FILES = (DEFAULT_TOKEN_FILE, "token.json", "token.pickle")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
DEFAULT_TARGET_CHANNEL = "MathRelaxing"


def _candidate_paths(base_dir: Path, env_name: str, defaults: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()

    def add(path_like: str | Path | None) -> None:
        if not path_like:
            return
        path = Path(path_like)
        if not path.is_absolute():
            path = base_dir / path
        key = str(path.resolve(strict=False)).lower()
        if key not in seen:
            seen.add(key)
            paths.append(path)

    add(os.environ.get(env_name))
    for default_name in defaults:
        add(default_name)
    return paths


def _required_scopes_present(creds: Credentials) -> bool:
    current_scopes = set(creds.scopes or [])
    return set(SCOPES).issubset(current_scopes)


def _load_credentials_from_file(token_path: Path) -> Credentials | None:
    try:
        if token_path.suffix.lower() == ".pickle":
            with token_path.open("rb") as handle:
                creds = pickle.load(handle)
        else:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except Exception:
        return None

    if not isinstance(creds, Credentials):
        return None
    if not _required_scopes_present(creds):
        return None
    return creds


def _save_credentials(creds: Credentials, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if token_path.suffix.lower() == ".pickle":
        with token_path.open("wb") as handle:
            pickle.dump(creds, handle)
        return

    with token_path.open("w", encoding="utf-8") as handle:
        handle.write(creds.to_json())


def _detect_client_secret_path(base_dir: Path) -> Path | None:
    for candidate in _candidate_paths(base_dir, "YOUTUBE_CLIENT_SECRET_FILE", DEFAULT_CLIENT_SECRET_FILES):
        if candidate.exists():
            return candidate
    return None


def _normalize_channel_name(value: str | None) -> str:
    cleaned = "".join(ch.lower() for ch in str(value or "").strip() if ch.isalnum())
    return cleaned


def _channel_matches(actual_channel: str | None, desired_channel: str | None) -> bool:
    if not desired_channel:
        return True
    return _normalize_channel_name(actual_channel) == _normalize_channel_name(desired_channel)


def _channel_token_filename(desired_channel: str | None) -> str | None:
    normalized = _normalize_channel_name(desired_channel)
    if not normalized:
        return None
    return f"token_youtube_{normalized}.json"


def _detect_token_paths(base_dir: Path, desired_channel: str | None = None) -> list[Path]:
    defaults: list[str] = []
    channel_token = _channel_token_filename(desired_channel)
    if channel_token:
        defaults.append(channel_token)
    defaults.extend(DEFAULT_TOKEN_FILES)
    return _candidate_paths(base_dir, "YOUTUBE_TOKEN_FILE", tuple(defaults))


def _get_channel_name_from_credentials(creds: Credentials) -> str:
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    response = youtube.channels().list(part="snippet", mine=True).execute()
    items = response.get("items", [])
    if not items:
        return "Canal sin nombre detectado"
    return str(items[0]["snippet"]["title"])


def get_youtube_credentials(
    *,
    force_reauth: bool = False,
    base_dir: Path | None = None,
    desired_channel: str | None = None,
) -> tuple[Credentials, Path, str]:
    if not GOOGLE_API_AVAILABLE:
        raise RuntimeError(
            "Faltan librerias de Google. Instala: "
            "pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    base_dir = base_dir or Path.cwd()
    desired_channel = str(desired_channel or os.environ.get("YOUTUBE_TARGET_CHANNEL", "")).strip()
    token_paths = _detect_token_paths(base_dir, desired_channel)
    client_secret_path = _detect_client_secret_path(base_dir)

    if not force_reauth:
        for token_path in token_paths:
            if not token_path.exists():
                continue
            creds = _load_credentials_from_file(token_path)
            if not creds:
                continue
            if creds.valid:
                try:
                    channel_name = _get_channel_name_from_credentials(creds)
                except Exception:
                    continue
                if _channel_matches(channel_name, desired_channel):
                    return creds, token_path, channel_name
                continue
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    channel_name = _get_channel_name_from_credentials(creds)
                    if not _channel_matches(channel_name, desired_channel):
                        continue
                    _save_credentials(creds, token_path)
                    return creds, token_path, channel_name
                except Exception:
                    continue

    if client_secret_path is None:
        file_list = ", ".join(DEFAULT_CLIENT_SECRET_FILES)
        raise FileNotFoundError(
            "No se encontro un OAuth client secret para YouTube. "
            f"Coloca uno de estos archivos en la carpeta del proyecto: {file_list}"
        )

    token_target = token_paths[0] if token_paths else (base_dir / DEFAULT_TOKEN_FILE)
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent select_account",
        access_type="offline",
        include_granted_scopes="false",
    )
    channel_name = _get_channel_name_from_credentials(creds)
    if desired_channel and not _channel_matches(channel_name, desired_channel):
        raise RuntimeError(
            f"Google autorizo el canal '{channel_name}', pero el canal objetivo es '{desired_channel}'. "
            "Pulsa 'Reautorizar' y en el flujo de Google elige el canal correcto."
        )
    _save_credentials(creds, token_target)
    return creds, token_target, channel_name


def _build_youtube_service(
    *,
    force_reauth: bool = False,
    desired_channel: str | None = None,
) -> tuple[object, Path, str]:
    creds, token_path, channel_name = get_youtube_credentials(
        force_reauth=force_reauth,
        desired_channel=desired_channel,
    )
    service = build("youtube", "v3", credentials=creds, cache_discovery=False)
    return service, token_path, channel_name


def _get_authorized_channel_name(*, force_reauth: bool = False, desired_channel: str | None = None) -> str:
    _, _, channel_name = _build_youtube_service(
        force_reauth=force_reauth,
        desired_channel=desired_channel,
    )
    return channel_name


def upload_video_to_youtube(
    *,
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str = "private",
    desired_channel: str | None = None,
    progress_callback=None,
    publish_at: str | None = None,
    thumbnail_path: str | None = None,
) -> tuple[str, str]:
    youtube, _, channel_name = _build_youtube_service(
        force_reauth=False,
        desired_channel=desired_channel,
    )

    # Garantiza el CTA de suscripción en TODA subida, incluidos los scripts
    # viejos que arman la descripción a mano. Idempotente: no duplica si ya está.
    try:
        from metadata import ensure_subscribe_cta
    except ImportError:  # pragma: no cover - fallback según sys.path
        try:
            from tools.metadata import ensure_subscribe_cta
        except ImportError:
            ensure_subscribe_cta = None
    if ensure_subscribe_cta is not None:
        description = ensure_subscribe_cta(description)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "28",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    
    if publish_at:
        body["status"]["publishAt"] = publish_at

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status and progress_callback is not None:
            progress_callback(int(status.progress() * 100))

    video_id = str(response["id"])
    
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            print(f"\nUploading thumbnail from {thumbnail_path}...")
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            print("Thumbnail uploaded successfully!")
        except Exception as e:
            print(f"\nFailed to upload thumbnail: {e}")

    return video_id, channel_name


def _read_object_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, tk.Variable):
        try:
            return str(value.get()).strip()
        except Exception:
            return ""
    if hasattr(value, "get"):
        try:
            return str(value.get()).strip()
        except TypeError:
            pass
        except Exception:
            return ""
        try:
            return str(value.get("1.0", "end-1c")).strip()
        except Exception:
            return ""
    return ""


def _extract_text_from_source(source_app, names: tuple[str, ...]) -> str:
    for name in names:
        if hasattr(source_app, name):
            text = _read_object_text(getattr(source_app, name))
            if text:
                return text
    return ""


def _extract_video_path(source_app) -> str:
    direct_names = (
        "generated_video_path",
        "last_generated_video_path",
        "last_video_path",
    )
    for name in direct_names:
        if hasattr(source_app, name):
            value = _read_object_text(getattr(source_app, name))
            if value and Path(value).exists():
                return value

    variable_names = (
        "youtube_video_path_var",
        "video_path_var",
        "output_video_var",
    )
    for name in variable_names:
        if hasattr(source_app, name):
            value = _read_object_text(getattr(source_app, name))
            if value and Path(value).exists():
                return value

    candidate_dirs: list[Path] = []
    output_dir_text = _extract_text_from_source(source_app, ("output_folder_var",))
    if output_dir_text:
        candidate_dirs.append(Path(output_dir_text))
    candidate_dirs.extend(
        [
            Path.cwd() / "_generated_videos",
            Path.cwd() / "_generated_videos_vector_fields",
        ]
    )

    video_files: list[Path] = []
    for directory in candidate_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                video_files.append(path)

    if not video_files:
        return ""

    newest_video = max(video_files, key=lambda path: path.stat().st_mtime)
    return str(newest_video)


def _default_title_from_video(video_path: str) -> str:
    if not video_path:
        return ""
    return Path(video_path).stem.replace("_", " ").strip()


class YouTubeUploadDialog:
    def __init__(self, source_app) -> None:
        self.source_app = source_app
        self.parent = getattr(source_app, "master", None) or source_app
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self.window = tk.Toplevel(self.parent)
        self.window.title("Subir Video a YouTube")
        self.window.geometry("760x560")
        self.window.minsize(640, 460)
        self.window.transient(self.parent)
        self.window.grab_set()

        self.video_var = tk.StringVar(value=_extract_video_path(source_app))
        self.title_var = tk.StringVar(
            value=_extract_text_from_source(
                source_app,
                ("yt_title_var", "yt_title_text", "title_var", "meta_title_var"),
            )
        )
        self.tags_var = tk.StringVar(
            value=_extract_text_from_source(
                source_app,
                ("yt_tags_var", "yt_tags_text", "tags_var", "meta_tags_var"),
            )
        )
        default_target_channel = (
            _extract_text_from_source(source_app, ("youtube_target_channel_var",))
            or os.environ.get("YOUTUBE_TARGET_CHANNEL", "").strip()
            or DEFAULT_TARGET_CHANNEL
        )
        self.target_channel_var = tk.StringVar(value=default_target_channel)
        self.privacy_var = tk.StringVar(value="private")
        self.account_var = tk.StringVar(value="Canal sin verificar")
        self.status_var = tk.StringVar(value="Listo para autenticar y subir.")

        self._build_ui()

        initial_description = _extract_text_from_source(source_app, ("yt_desc_text", "desc_text", "meta_desc_text"))
        self.desc_text.insert("1.0", initial_description)

        if not self.title_var.get().strip():
            self.title_var.set(_default_title_from_video(self.video_var.get()))

        if not GOOGLE_API_AVAILABLE:
            warning = (
                "Faltan librerias de Google. Instala: "
                "pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
            self.status_var.set(warning)
            self.verify_button.configure(state="disabled")
            self.reauth_button.configure(state="disabled")
            self.upload_button.configure(state="disabled")

        self.window.after(120, self._poll_queue)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Video:").grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(frame, textvariable=self.video_var).grid(row=0, column=1, sticky="ew", pady=(0, 8))
        ttk.Button(frame, text="Examinar", command=self._browse_video).grid(row=0, column=2, padx=(8, 0), pady=(0, 8))

        ttk.Label(frame, text="Titulo:").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.title_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=8)

        ttk.Label(frame, text="Descripcion:").grid(row=2, column=0, sticky="nw", pady=8)
        self.desc_text = scrolledtext.ScrolledText(frame, width=70, height=10, wrap=tk.WORD)
        self.desc_text.grid(row=2, column=1, columnspan=2, sticky="nsew", pady=8)

        ttk.Label(frame, text="Tags:").grid(row=3, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.tags_var).grid(row=3, column=1, columnspan=2, sticky="ew", pady=8)

        ttk.Label(frame, text="Privacidad:").grid(row=4, column=0, sticky="w", pady=8)
        ttk.Combobox(
            frame,
            textvariable=self.privacy_var,
            values=("private", "unlisted", "public"),
            state="readonly",
            width=18,
        ).grid(row=4, column=1, sticky="w", pady=8)

        ttk.Label(frame, text="Canal objetivo:").grid(row=5, column=0, sticky="w", pady=(8, 4))
        ttk.Entry(frame, textvariable=self.target_channel_var).grid(row=5, column=1, columnspan=2, sticky="ew", pady=(8, 4))

        ttk.Label(frame, text="Canal autorizado:").grid(row=6, column=0, sticky="w", pady=(8, 4))
        ttk.Label(frame, textvariable=self.account_var, wraplength=520).grid(
            row=6, column=1, columnspan=2, sticky="w", pady=(8, 4)
        )

        ttk.Label(frame, textvariable=self.status_var, wraplength=680).grid(
            row=7, column=0, columnspan=3, sticky="ew", pady=(10, 4)
        )

        button_row = ttk.Frame(frame)
        button_row.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(14, 0))

        self.verify_button = ttk.Button(button_row, text="Verificar canal", command=self._verify_account)
        self.verify_button.pack(side=tk.LEFT)
        self.reauth_button = ttk.Button(button_row, text="Reautorizar", command=self._reauthorize_channel)
        self.reauth_button.pack(side=tk.LEFT, padx=(8, 0))
        self.upload_button = ttk.Button(button_row, text="Subir a YouTube", command=self._start_upload)
        self.upload_button.pack(side=tk.RIGHT)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.verify_button.configure(state=state)
        self.reauth_button.configure(state=state)
        self.upload_button.configure(state=state)

    def _browse_video(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.window,
            title="Selecciona un video para YouTube",
            filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("Todos", "*.*")],
        )
        if path:
            self.video_var.set(path)
            if not self.title_var.get().strip():
                self.title_var.set(_default_title_from_video(path))

    def _verify_account(self) -> None:
        self._run_in_thread(self._verify_account_worker, force_reauth=False)

    def _reauthorize_channel(self) -> None:
        if not messagebox.askyesno(
            "Reautorizar canal",
            "Se abrira el navegador para autorizar otro canal de YouTube. Quieres continuar?",
            parent=self.window,
        ):
            return
        self._run_in_thread(self._verify_account_worker, force_reauth=True)

    def _verify_account_worker(self, *, force_reauth: bool) -> None:
        action = "Reautorizando canal..." if force_reauth else "Verificando canal..."
        self.queue.put(("status", action))
        channel_name = _get_authorized_channel_name(
            force_reauth=force_reauth,
            desired_channel=self.target_channel_var.get().strip(),
        )
        self.queue.put(("account", channel_name))
        self.queue.put(("status", f"Canal autorizado: {channel_name}"))
        self.queue.put(("buttons", True))

    def _start_upload(self) -> None:
        video_path = self.video_var.get().strip()
        title = self.title_var.get().strip()
        description = self.desc_text.get("1.0", "end-1c").strip()
        if not video_path or not Path(video_path).exists():
            messagebox.showerror("Error", "Selecciona un video valido antes de subir.", parent=self.window)
            return
        if not title:
            messagebox.showerror("Error", "El titulo no puede estar vacio.", parent=self.window)
            return
        if not description:
            messagebox.showerror("Error", "La descripcion no puede estar vacia.", parent=self.window)
            return

        self._run_in_thread(
            self._upload_worker,
            video_path=video_path,
            title=title,
            description=description,
            tags=self.tags_var.get(),
            privacy_status=self.privacy_var.get(),
            desired_channel=self.target_channel_var.get().strip(),
        )

    def _upload_worker(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
        tags: str,
        privacy_status: str,
        desired_channel: str,
    ) -> None:
        self.queue.put(("status", "Preparando subida a YouTube..."))

        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        def on_progress(progress: int) -> None:
            self.queue.put(("status", f"Subiendo video... {progress}%"))

        video_id, channel_name = upload_video_to_youtube(
            video_path=video_path,
            title=title,
            description=description,
            tags=tag_list,
            privacy_status=privacy_status,
            desired_channel=desired_channel,
            progress_callback=on_progress,
        )
        self.queue.put(("account", channel_name))
        self.queue.put(("success", (video_id, channel_name)))
        self.queue.put(("buttons", True))

    def _run_in_thread(self, worker, **kwargs) -> None:
        if not GOOGLE_API_AVAILABLE:
            return

        self._set_buttons_enabled(False)

        def run() -> None:
            try:
                worker(**kwargs)
            except Exception as exc:
                self.queue.put(("error", str(exc)))
                self.queue.put(("buttons", True))

        threading.Thread(target=run, daemon=True).start()

    def _poll_queue(self) -> None:
        if not self.window.winfo_exists():
            return

        try:
            while True:
                kind, value = self.queue.get_nowait()
                if kind == "status":
                    self.status_var.set(str(value))
                elif kind == "account":
                    self.account_var.set(str(value))
                elif kind == "buttons":
                    self._set_buttons_enabled(bool(value))
                elif kind == "success":
                    video_id, channel_name = value
                    url = f"https://youtu.be/{video_id}"
                    self.status_var.set(f"Subida completa en {channel_name}: {url}")
                    messagebox.showinfo(
                        "YouTube",
                        f"Video subido correctamente.\n\nCanal: {channel_name}\nURL: {url}",
                        parent=self.window,
                    )
                elif kind == "error":
                    self.status_var.set(f"Error: {value}")
                    messagebox.showerror("Error", str(value), parent=self.window)
        except queue.Empty:
            pass

        self.window.after(120, self._poll_queue)


def open_youtube_upload_dialog(source_app) -> None:
    YouTubeUploadDialog(source_app)
