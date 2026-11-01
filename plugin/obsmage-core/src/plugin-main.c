/* obsmage-core -- the core obsmage plugin.
 *
 * Always loaded, even when no feature-module plugins are installed. It owns two Tools-menu
 * entries:
 *   "obsmage: compose screen maps"   (the multi-head composer; for now it runs
 *                                     tools/omg_compose.py on the current scene collection)
 *   "obsmage: calibrate cameras"     (AR calibration; designed in docs/AR-CONTROL.md, not built)
 * On OBS_FRONTEND_EVENT_FINISHED_LOADING it audits display bindings, logs what it found and
 * changes nothing; composing is always the person's choice.
 *
 * STATUS: skeleton. It compiles against the public libobs/frontend API as written, but has not
 * been built or loaded in CI yet. Treat every behaviour beyond logging as TODO.
 */
#include <obs-module.h>
#include <obs-frontend-api.h>
#include <util/platform.h>

OBS_DECLARE_MODULE()
OBS_MODULE_USE_DEFAULT_LOCALE("obsmage-core", "en-US")

#define LOG(level, fmt, ...) blog(level, "[obsmage-core] " fmt, ##__VA_ARGS__)

static void compose_screen_maps(void *data)
{
	(void)data;
	char *collection = obs_frontend_get_current_scene_collection();
	LOG(LOG_INFO, "compose requested for collection '%s' (TODO: run the composer, show its "
		      "words-first diff, write only on the person's yes)",
	    collection ? collection : "(none)");
	bfree(collection);
}

static void calibrate_cameras(void *data)
{
	(void)data;
	LOG(LOG_INFO, "calibration requested (TODO: the four-step dock in docs/AR-CONTROL.md)");
}

static void on_event(enum obs_frontend_event event, void *data)
{
	(void)data;
	if (event == OBS_FRONTEND_EVENT_FINISHED_LOADING)
		LOG(LOG_INFO, "loaded; display-binding audit runs here (read-only)");
}

bool obs_module_load(void)
{
	obs_frontend_add_tools_menu_item(obs_module_text("ComposeScreenMaps"), compose_screen_maps, NULL);
	obs_frontend_add_tools_menu_item(obs_module_text("CalibrateCameras"), calibrate_cameras, NULL);
	obs_frontend_add_event_callback(on_event, NULL);
	LOG(LOG_INFO, "version %s", "0.0.1");
	return true;
}

void obs_module_unload(void)
{
	obs_frontend_remove_event_callback(on_event, NULL);
}

const char *obs_module_description(void)
{
	return "obsmage core: screen-map composer and AR calibration entry points";
}

/* Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
 * Mentat (for Corwin; claude-opus-5-5) */
