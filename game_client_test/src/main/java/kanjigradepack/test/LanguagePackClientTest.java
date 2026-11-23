package kanjigradepack.test;

import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.lang.reflect.Constructor;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Options;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.packs.PackSelectionScreen;
import net.minecraft.client.gui.screens.options.LanguageSelectScreen;
import net.minecraft.client.gui.screens.options.OptionsScreen;
import net.minecraft.locale.DeprecatedTranslationsInfo;
import net.minecraft.locale.Language;
import net.minecraft.network.chat.Component;
import net.minecraft.server.packs.repository.PackCompatibility;
import net.minecraft.server.packs.repository.PackRepository;

/**
 * Checks the pack in a production client: the game takes the pack as made for this version (its resource pack format),
 * it turns the pack on, finds the languages of its pack.mcmeta in the language list, and for each language checks that
 * every string of its file in the pack is the string the game uses. Screenshots of the title screen and the options
 * screen in each language, of the language list (with the languages of the pack) and of the resource pack list (the
 * pack's icon) go to run/<Minecraft version>/screenshots/ (the screenshots of README.md come from them).
 */
public class LanguagePackClientTest implements FabricClientGameTest {
	private static final int RELOAD_TIMEOUT = 2400;
	// The loading overlay fades out in about one second after the reload
	private static final int OVERLAY_FADE_TICKS = 40;
	// The language selected when the language list is shot: the list is in the order of the codes (ja_g1 ... ja_g6,
	// ja_jp, ja_kana) and shows the selected one in its fifth row, so all of them are in the shot
	private static final String LANGUAGE_OF_THE_LIST = "ja_g5";
	private static final int SCREENSHOT_WIDTH = 1920;
	private static final int SCREENSHOT_HEIGHT = 1080;

	@Override
	public void runTest(ClientGameTestContext context) {
		Path pack = Path.of(System.getProperty("kanji_grade_language_pack.pack"));
		List<String> languages = readLanguageCodes(pack);
		if (languages.size() != 7) {
			throw new AssertionError("pack.mcmeta has " + languages.size() + " languages: " + languages);
		}
		Map<String, Map<String, String>> expected = readLanguages(pack, languages);
		String packId = "file/" + pack.getFileName();
		// Full HD: the GUI scale (auto) is 4, so the screenshots are sharp enough for README.md and the pack's icon is shown
		// at its own size (128 x 128)
		context.getInput().resizeWindow(SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT);

		CompletableFuture<Void> packReload = context.computeOnClient(minecraft -> {
			PackRepository packs = minecraft.getResourcePackRepository();
			packs.reload();
			if (!packs.isAvailable(packId)) {
				throw new AssertionError(packId + " is not available: " + packs.getAvailableIds());
			}
			// The resource pack format of pack.mcmeta is the one of this Minecraft version
			PackCompatibility compatibility = packs.getPack(packId).getCompatibility();
			if (!compatibility.isCompatible()) {
				throw new AssertionError(packId + " is not made for this version: " + compatibility);
			}
			packs.addPack(packId);
			minecraft.options.resourcePacks.add(packId);
			return minecraft.reloadResourcePacks();
		});
		waitForReload(context, packReload);

		context.runOnClient(minecraft -> {
			for (String code : languages) {
				if (minecraft.getLanguageManager().getLanguage(code) == null) {
					throw new AssertionError(code + " is not in the language list: "
						+ minecraft.getLanguageManager().getLanguages().keySet());
				}
			}
		});

		for (String code : languages) {
			selectLanguage(context, code);
			List<String> wrong = context.computeOnClient(minecraft -> {
				Language language = Language.getInstance();
				List<String> out = new ArrayList<>();
				expected.get(code).forEach((key, text) -> {
					String got = language.getOrDefault(key, null);
					if (!text.equals(got)) {
						out.add(key + ": expected " + text + ", got " + got);
					}
				});
				return out;
			});
			if (!wrong.isEmpty()) {
				throw new AssertionError(code + ": " + wrong.size() + " of " + expected.get(code).size()
					+ " strings differ, e.g. " + wrong.subList(0, Math.min(5, wrong.size())));
			}
			context.setScreen(TitleScreen::new);
			takeScreenshot(context, "title_" + code);
			context.setScreen(LanguagePackClientTest::optionsScreen);
			takeScreenshot(context, "options_" + code);
		}

		selectLanguage(context, LANGUAGE_OF_THE_LIST);
		context.setScreen(() -> {
			Minecraft minecraft = Minecraft.getInstance();
			return new LanguageSelectScreen(new TitleScreen(), minecraft.options, minecraft.getLanguageManager());
		});
		takeScreenshot(context, "language_list");

		// The resource pack list, where the pack shows its icon (pack.png) and description
		context.setScreen(() -> {
			Minecraft minecraft = Minecraft.getInstance();
			return new PackSelectionScreen(minecraft.getResourcePackRepository(), packs -> {},
				minecraft.getResourcePackDirectory(), Component.translatable("resourcePack.title"));
		});
		takeScreenshot(context, "resource_packs");
		// A client GameTest has to end on the title screen
		context.setScreen(TitleScreen::new);
	}

	/**
	 * A screenshot with the cursor at the bottom edge of the window, below every button and list, so nothing in it is
	 * shown as hovered (the window's centre, where the cursor is otherwise, is on a button of most screens).
	 */
	private static void takeScreenshot(ClientGameTestContext context, String name) {
		context.getInput().setCursorPos(SCREENSHOT_WIDTH / 2.0, SCREENSHOT_HEIGHT - 1);
		context.waitTick();
		context.takeScreenshot(name);
	}

	/**
	 * The options screen, opened from the title screen. Its constructor differs between versions: (Screen, Options,
	 * boolean inWorld) in 26.1, (Screen, Options) from 26.2; the test is compiled for each version, so it picks the one
	 * there is.
	 */
	private static Screen optionsScreen() {
		Options options = Minecraft.getInstance().options;
		for (Constructor<?> constructor : OptionsScreen.class.getConstructors()) {
			List<Class<?>> parameters = Arrays.asList(constructor.getParameterTypes());
			try {
				if (parameters.equals(List.of(Screen.class, Options.class))) {
					return (Screen) constructor.newInstance(new TitleScreen(), options);
				}
				if (parameters.equals(List.of(Screen.class, Options.class, boolean.class))) {
					return (Screen) constructor.newInstance(new TitleScreen(), options, false);
				}
			} catch (ReflectiveOperationException e) {
				throw new AssertionError("cannot open the options screen", e);
			}
		}
		throw new AssertionError("no known constructor of OptionsScreen: "
			+ Arrays.toString(OptionsScreen.class.getConstructors()));
	}

	/** Selects a language as the language screen does, and waits for the game to load it. */
	private static void selectLanguage(ClientGameTestContext context, String code) {
		CompletableFuture<Void> reload = context.computeOnClient(minecraft -> {
			minecraft.getLanguageManager().setSelected(code);
			minecraft.options.languageCode = code;
			return minecraft.reloadResourcePacks();
		});
		waitForReload(context, reload);
	}

	/**
	 * Waits for a reload of the resources, then for the loading overlay to fade out. Only the future is waited for, not
	 * the overlay itself: where the game keeps the overlay changed between versions (Minecraft.getOverlay() in 26.1,
	 * Gui.overlay() from 26.2), and the test runs on all of them.
	 */
	private static void waitForReload(ClientGameTestContext context, CompletableFuture<Void> reload) {
		context.waitFor(minecraft -> reload.isDone(), RELOAD_TIMEOUT);
		reload.join();
		context.waitTicks(OVERLAY_FADE_TICKS);
	}

	/** The language codes of pack.mcmeta, in its order. */
	private static List<String> readLanguageCodes(Path pack) {
		try (ZipFile zip = new ZipFile(pack.toFile());
				Reader reader = new InputStreamReader(zip.getInputStream(zip.getEntry("pack.mcmeta")), StandardCharsets.UTF_8)) {
			return new ArrayList<>(JsonParser.parseReader(reader).getAsJsonObject().getAsJsonObject("language").keySet());
		} catch (IOException e) {
			throw new AssertionError("cannot read pack.mcmeta of " + pack, e);
		}
	}

	/**
	 * {language code: {key: text}} from assets/minecraft/lang/ of the pack, after the game's own change to every language
	 * it loads (ClientLanguage.loadFrom): keys it no longer uses removed, renamed keys moved to their new names.
	 */
	private static Map<String, Map<String, String>> readLanguages(Path pack, List<String> languages) {
		Map<String, Map<String, String>> out = new LinkedHashMap<>();
		try (ZipFile zip = new ZipFile(pack.toFile())) {
			for (String code : languages) {
				ZipEntry entry = zip.getEntry("assets/minecraft/lang/" + code + ".json");
				if (entry == null) {
					throw new AssertionError(code + ".json is not in " + pack);
				}
				Map<String, String> strings = new LinkedHashMap<>();
				try (Reader reader = new InputStreamReader(zip.getInputStream(entry), StandardCharsets.UTF_8)) {
					for (Map.Entry<String, JsonElement> e : JsonParser.parseReader(reader).getAsJsonObject().entrySet()) {
						strings.put(e.getKey(), e.getValue().getAsString());
					}
				}
				DeprecatedTranslationsInfo.loadFromDefaultResource().applyToMap(strings);
				out.put(code, strings);
			}
		} catch (IOException e) {
			throw new AssertionError("cannot read " + pack, e);
		}
		return out;
	}
}
