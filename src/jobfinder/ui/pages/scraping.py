"""Page « Scraping & réglages » : configuration complète et lancement d'une mise à jour.

Les champs du formulaire sont liés directement à l'objet de configuration (bind_value) :
modifier un champ modifie `config`, et « Enregistrer » écrit config.json.
Le scraping tourne en tâche de fond : on peut changer de page et revenir suivre
l'avancement (rafraîchi chaque seconde).
"""
import shutil

from nicegui import ui

from jobfinder.config import API_KEY_ENV_VARS, PLATFORM_KEYS, get_api_key, load_config, save_config, set_api_key
from jobfinder.llm import PROMPT_TEMPLATE
from jobfinder.models import PLATFORM_LABELS
from jobfinder.paths import CONFIG_PATH, DEFAULT_CONFIG_PATH
from jobfinder.ui import services
from jobfinder.ui.layout import page_frame

LANGUAGES = {"fr": "Français", "en": "Anglais", "autre": "Autres langues"}


def section(title: str, icon: str, caption: str = "", opened: bool = False):
    """Bloc repliable du formulaire."""
    return ui.expansion(title, icon=icon, caption=caption, value=opened) \
        .classes("w-full").props("header-class='text-subtitle1 font-medium' switch-toggle-side=false")


@ui.page("/scraping")
def scraping_page() -> None:
    nav = page_frame("Scraping & réglages", "/scraping")
    config = load_config()

    with ui.row().classes("w-full no-wrap items-start gap-4"):
        # ================================================================ formulaire
        with ui.card().classes("grow min-w-0"):
            with section("Mots-clés", "key", "Un mot-clé par ligne", opened=True):
                keywords = ui.textarea(value="\n".join(config.keywords)).props("outlined autogrow").classes("w-full")

            with section("Plateformes", "public", "URL de recherche copiée depuis chaque site, filtres compris"):
                for key in PLATFORM_KEYS:
                    config.url.setdefault(key, "")
                    config.launch_scrap.setdefault(key, False)
                    with ui.row().classes("w-full items-center no-wrap gap-3"):
                        ui.switch(PLATFORM_LABELS[key]).bind_value(config.launch_scrap, key).classes("w-44 shrink-0")
                        ui.input("URL de recherche").bind_value(config.url, key).props("dense outlined").classes("grow")

            with section("Filtres avant le LLM", "filter_alt", "Ancienneté, langues, mots exclus ou requis"):
                ui.number("Ancienneté maximale des offres (jours)", min=1, precision=0, format="%d") \
                    .bind_value(config, "filter_day_scrap", forward=lambda v: int(v or 1)).classes("w-80")
                with ui.row().classes("items-center gap-4"):
                    ui.label("Langues acceptées :")
                    for code, label in LANGUAGES.items():
                        config.language_filter.setdefault(code, False)
                        ui.checkbox(label).bind_value(config.language_filter, code)
                ui.switch("Activer le pré-filtre par mots").bind_value(config.pre_filter, "enabled")
                with ui.column().classes("w-full").bind_visibility_from(config.pre_filter, "enabled"):
                    ui.input_chips("Mots exclus (offre écartée si présent)").bind_value(config.pre_filter, "blacklist") \
                        .classes("w-full")
                    ui.input_chips("Mots requis (au moins un)").bind_value(config.pre_filter, "whitelist") \
                        .classes("w-full")
                ui.label("Les offres écartées par ces filtres sont conservées avec un score de 0 "
                         "(onglet « Écartées »).").classes("text-caption text-grey-7")

            with section("Évaluation par LLM", "psychology", "Score de 0 à 100 selon vos critères"):
                ui.switch("Évaluer les nouvelles offres avec un LLM").bind_value(config, "use_llm")
                with ui.column().classes("w-full gap-3").bind_visibility_from(config, "use_llm"):
                    ui.toggle({"Local": "Local (Ollama)", "ChatGPT": "ChatGPT", "Mistral": "Mistral"}) \
                        .bind_value(config.llm, "provider")
                    ui.input("Modèle Ollama").bind_value(config.llm, "ollama_model").props("dense outlined") \
                        .classes("w-80").bind_visibility_from(config.llm, "provider", value="Local")
                    api_key = ui.input("Clé API (enregistrée dans le fichier .env)", password=True,
                                       password_toggle_button=True).props("dense outlined").classes("w-96")
                    api_key.bind_visibility_from(config.llm, "provider", backward=lambda p: p in API_KEY_ENV_VARS)

                    ui.textarea("Vos critères de recherche").bind_value(config.llm, "search_criteria") \
                        .props("outlined autogrow").classes("w-full")
                    ui.label("Décrivez uniquement ce que vous voulez, tolérez et refusez. Le barème de 0 à 100 "
                             "et le format de réponse sont ajoutés automatiquement.").classes("text-caption text-grey-7")
                    with ui.expansion("Voir le prompt complet envoyé au LLM", icon="visibility").classes("w-full"):
                        @ui.refreshable
                        def full_prompt() -> None:
                            ui.code(PROMPT_TEMPLATE.format(criteria=config.llm.search_criteria.strip(),
                                                           company="<entreprise>", title="<intitulé>",
                                                           content="<description de l'offre>"),
                                    language="text").classes("w-full")
                        full_prompt()
                        ui.button("Actualiser", icon="refresh", on_click=full_prompt.refresh).props("flat dense")

                    ui.number("Seuil de pertinence (score minimum pour « À traiter »)", min=0, max=100, precision=0) \
                        .bind_value(config.llm, "score_threshold", forward=lambda v: int(v or 0)).classes("w-96")

            with section("Suivi des candidatures", "event", "Rappel de relance"):
                ui.number("Relance conseillée après (jours sans nouvelle)", min=1, precision=0) \
                    .bind_value(config, "follow_up_days", forward=lambda v: int(v or 1)).classes("w-96")
                ui.switch("Scraper les plateformes en parallèle").bind_value(config, "use_multithreading")

            def save() -> bool:
                """Enregistre la configuration. Renvoie False si elle est invalide."""
                config.keywords = [k.strip() for k in keywords.value.splitlines() if k.strip()]
                if api_key.value:
                    set_api_key(config.llm.provider, api_key.value)
                    api_key.value = ""
                try:
                    save_config(config)
                except Exception as exc:
                    ui.notify(f"Configuration invalide : {exc}", type="negative")
                    return False
                full_prompt.refresh()
                return True

            def reset() -> None:
                shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
                ui.navigate.reload()

            def save_and_confirm() -> None:
                if save():
                    ui.notify("Configuration enregistrée", type="positive")

            with ui.row().classes("w-full justify-end q-mt-md"):
                ui.button("Réinitialiser", icon="restart_alt", on_click=reset).props("flat color=grey-8")
                ui.button("Enregistrer", icon="save", on_click=save_and_confirm)

        # ============================================================= lancement
        with ui.card().classes("w-[26rem] shrink-0 sticky top-20"):
            ui.label("Mise à jour des offres").classes("text-h6")

            def launch() -> None:
                if not save():
                    return
                errors = config.scraping_errors()
                if config.use_llm and config.llm.provider in API_KEY_ENV_VARS and not get_api_key(config.llm.provider):
                    errors.append(f"Clé API {config.llm.provider} manquante.")
                if errors:
                    ui.notify(" ".join(errors), type="warning", multi_line=True)
                    return
                services.start_scraping()
                progress_view.refresh()
                nav.refresh()

            launch_button = ui.button("Enregistrer et lancer", icon="play_arrow", on_click=launch).classes("w-full")

            @ui.refreshable
            def progress_view() -> None:
                run = services.scraping
                launch_button.set_enabled(not run.running)
                if run.task is None:
                    ui.label("Aucune mise à jour lancée depuis le démarrage de l'application.") \
                        .classes("text-grey-7")
                    return
                for name, task in run.progress.tasks.items():
                    with ui.column().classes("w-full gap-1"):
                        with ui.row().classes("w-full justify-between text-body2"):
                            ui.label(name).classes("font-medium")
                            ui.label(task.detail or (f"{task.current} / {task.total}" if task.total else task.state)) \
                                .classes("text-grey-7 ellipsis max-w-[14rem]")
                        color = {"erreur": "negative", "terminé": "positive"}.get(task.state, "primary")
                        ui.linear_progress(task.ratio, show_value=False, color=color).props("rounded size=8px")
                if run.error:
                    ui.label(f"Erreur : {run.error}").classes("text-negative")
                if run.report and not run.running:
                    r = run.report
                    with ui.card().props("flat bordered").classes("w-full tint-primary"):
                        ui.label(f"{r.inserted} nouvelle(s) offre(s) enregistrée(s)").classes("font-medium")
                        ui.label(f"{r.wrong_language} hors langue · {r.pre_filtered} pré-filtrée(s) · "
                                 f"{r.scored} évaluée(s) par le LLM"
                                 + (f" · {r.llm_failures} échec(s) LLM" if r.llm_failures else ""))
                        ui.button("Voir les offres", icon="inbox", on_click=lambda: ui.navigate.to("/offres")) \
                            .props("flat dense")
                with ui.expansion("Journal", icon="list").classes("w-full"):
                    for message in run.progress.messages[-30:]:
                        ui.label(message).classes("text-caption font-mono")

            progress_view()

            state = {"was_running": services.scraping.running}

            def tick() -> None:
                """Rafraîchit l'avancement pendant le scraping, puis une dernière fois à la fin."""
                running = services.scraping.running
                if running or state["was_running"]:
                    progress_view.refresh()
                if state["was_running"] and not running:
                    nav.refresh()  # compteurs du menu à jour
                state["was_running"] = running

            ui.timer(1.0, tick)
