package kanjigradepack.test;

import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import net.fabricmc.fabric.api.client.gametest.v1.FabricClientGameTest;
import net.fabricmc.fabric.api.client.gametest.v1.context.ClientGameTestContext;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.packs.PackSelectionScreen;
import net.minecraft.client.gui.screens.options.LanguageSelectScreen;
import net.minecraft.locale.DeprecatedTranslationsInfo;
import net.minecraft.locale.Language;
import net.minecraft.network.chat.Component;
import net.minecraft.server.packs.repository.PackCompatibility;
import net.minecraft.server.packs.repository.PackRepository;

/**
 * Checks the pack in a production client: the game takes the pack as made for this version (its resource pack format),
 * it turns the pack on, finds the languages of its pack.mcmeta in the language list, and for each language checks that
 * every string of its file in the pack is the string the game uses. Screenshots of the
 * language list, of the title screen in each language and of the resource pack list (the pack's icon) go to
 * run/<Minecraft version>/screenshots/.
 */
public class LanguagePackClientTest implements FabricClientGameTest {
	private static final int RELOAD_TIMEOUT = 2400;
	// The loading overlay fades out in about one second after the reload
	private static final int OVERLAY_FADE_TICKS = 40;

	@Override
	public void runTest(ClientGameTestContext context) {
		Path pack = Path.of(System.getProperty("kanji_grade_language_pack.pack"));
		List<String> languages = readLanguageCodes(pack);
		if (languages.size() != 7) {
			throw new AssertionError("pack.mcmeta has " + languages.size() + " languages: " + languages);
		}
		Map<String, Map<String, String>> expected = readLanguages(pack, languages);
		String packId = "file/" + pack.getFileName();

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
		context.setScreen(() -> {
			Minecraft minecraft = Minecraft.getInstance();
			return new LanguageSelectScreen(new TitleScreen(), minecraft.options, minecraft.getLanguageManager());
		});
		// The names of the seven languages have full-width brackets (日本語（3年生）): typed into the search box, they
		// leave the seven (and other languages with such brackets) in the list
		context.getInput().typeChars("（");
		context.waitTick();
		context.takeScreenshot("language_list");

		for (String code : languages) {
			CompletableFuture<Void> languageReload = context.computeOnClient(minecraft -> {
				minecraft.getLanguageManager().setSelected(code);
				minecraft.options.languageCode = code;
				return minecraft.reloadResourcePacks();
			});
			waitForReload(context, languageReload);
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
			context.takeScreenshot("title_" + code);
		}

		// The resource pack list, where the pack shows its icon (pack.png) and description
		context.setScreen(() -> {
			Minecraft minecraft = Minecraft.getInstance();
			return new PackSelectionScreen(minecraft.getResourcePackRepository(), packs -> {},
				minecraft.getResourcePackDirectory(), Component.translatable("resourcePack.title"));
		});
		context.takeScreenshot("resource_packs");
		// A client GameTest has to end on the title screen
		context.setScreen(TitleScreen::new);
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
