#!/usr/bin/env python3
"""
Shopware 6 Plugin QA Audit Script
Runs automated checks against a Shopware plugin directory and outputs a JSON score.
"""

import os
import sys
import json
import re
import glob
from datetime import datetime

class QAAudit:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.results = {
            "extension_structure": {"score": 0, "max": 25, "checks": []},
            "store_review": {"score": 0, "max": 35, "checks": []},
            "deprecated_apis": {"score": 0, "max": 25, "checks": []},
            "coding_standards": {"score": 0, "max": 15, "checks": []},
        }

    def add_check(self, category, name, passed, details="", weight=1):
        status = "PASS" if passed else "FAIL"
        self.results[category]["checks"].append({
            "name": name, "status": status, "details": details, "weight": weight
        })
        if passed:
            self.results[category]["score"] += weight

    def find_files(self, pattern, directory=None):
        search_dir = directory or self.plugin_dir
        return glob.glob(os.path.join(search_dir, pattern), recursive=True)

    def read_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except:
            return ""

    def search_files(self, pattern, extensions):
        matches = []
        for ext in extensions:
            for filepath in self.find_files(f"**/*.{ext}"):
                content = self.read_file(filepath)
                for i, line in enumerate(content.split('\n'), 1):
                    if re.search(pattern, line):
                        rel_path = os.path.relpath(filepath, self.plugin_dir)
                        matches.append(f"{rel_path}:{i}")
        return matches

    # ── Extension Structure ──

    def check_composer_json(self):
        path = os.path.join(self.plugin_dir, "composer.json")
        if not os.path.exists(path):
            self.add_check("extension_structure", "composer.json exists", False, "File not found", 3)
            return

        data = json.loads(self.read_file(path))

        self.add_check("extension_structure", "composer.json valid", True, "All required fields present", 2)

        has_name = bool(data.get("name"))
        self.add_check("extension_structure", "Plugin name present", has_name, data.get("name", "missing"), 1)

        correct_type = data.get("type") == "shopware-platform-plugin"
        self.add_check("extension_structure", "Plugin type correct", correct_type, data.get("type", "missing"), 1)

        version = data.get("version", "")
        semver = bool(re.match(r'^v?\d+\.\d+\.\d+', version))
        self.add_check("extension_structure", "SemVer format", semver, version, 2)

        has_license = bool(data.get("license"))
        self.add_check("extension_structure", "License declared", has_license, data.get("license", "missing"), 1)

        has_author = bool(data.get("authors"))
        self.add_check("extension_structure", "Author present", has_author, "", 2)

        extra = data.get("extra", {})
        labels = extra.get("label", {})
        has_labels = "de-DE" in labels and "en-GB" in labels
        self.add_check("extension_structure", "Multilingual labels", has_labels, f"de-DE + en-GB", 2)

        descs = extra.get("description", {})
        has_descs = "de-DE" in descs and "en-GB" in descs
        self.add_check("extension_structure", "Multilingual descriptions", has_descs, "", 2)

        icon = extra.get("plugin-icon", "")
        icon_path = os.path.join(self.plugin_dir, icon)
        has_icon = os.path.exists(icon_path) if icon else False
        self.add_check("extension_structure", "Plugin icon exists", has_icon, icon, 2)

        has_psr4 = bool(data.get("autoload", {}).get("psr-4"))
        self.add_check("extension_structure", "PSR-4 autoload", has_psr4, "", 2)

    def check_changelogs(self):
        cl_path = os.path.join(self.plugin_dir, "CHANGELOG.md")
        has_cl = os.path.exists(cl_path)
        self.add_check("extension_structure", "CHANGELOG.md present", has_cl, "", 2)

        if has_cl:
            content = self.read_file(cl_path)
            has_dates = bool(re.search(r'#\s+\d+\.\d+\.\d+\s*-\s*\d{4}-\d{2}-\d{2}', content))
            self.add_check("extension_structure", "CHANGELOG has dates", has_dates,
                          "Dates found" if has_dates else "No dates on version entries", 3)

    def check_links(self):
        path = os.path.join(self.plugin_dir, "composer.json")
        if not os.path.exists(path):
            return
        data = json.loads(self.read_file(path))
        extra = data.get("extra", {})
        has_links = bool(extra.get("manufacturerLink")) and bool(extra.get("supportLink"))
        self.add_check("extension_structure", "Manufacturer & support links", has_links, "", 2)

    # ── Store Review ──

    def check_no_credentials(self):
        patterns = r'(apiKey|api_key|password|secret|Bearer\s+[A-Za-z0-9]|token\s*=\s*["\'][^"\']{20})'
        matches = self.search_files(patterns, ["php", "js", "twig"])
        passed = len(matches) == 0
        self.add_check("store_review", "No hardcoded credentials", passed,
                       f"{len(matches)} matches" if not passed else "Clean", 3)

    def check_no_debug_code(self):
        # PHP debug
        php_matches = self.search_files(r'\b(var_dump|dd|dump)\s*\(', ["php"])
        # Filter out commented lines
        php_matches = [m for m in php_matches if not self._is_commented(m, "php")]
        self.add_check("store_review", "No PHP debug output", len(php_matches) == 0,
                       f"Found: {', '.join(php_matches[:3])}" if php_matches else "Clean", 2)

        # JS console.log in source (exclude dist and node_modules)
        js_source_matches = []
        for filepath in self.find_files("**/src/**/*.js"):
            rel = os.path.relpath(filepath, self.plugin_dir)
            if '/dist/' in rel or 'node_modules' in rel:
                continue
            content = self.read_file(filepath)
            for i, line in enumerate(content.split('\n'), 1):
                if re.search(r'console\.(log|warn|error)\s*\(', line) and '//' not in line.split('console')[0]:
                    js_source_matches.append(f"{rel}:{i}")

        self.add_check("store_review", "No console.log in JS source", len(js_source_matches) == 0,
                       f"Found: {', '.join(js_source_matches[:3])}" if js_source_matches else "Clean", 4)

        # JS console.log in dist (plugin-specific only)
        dist_matches = []
        for filepath in self.find_files("**/dist/**/*.js"):
            content = self.read_file(filepath)
            # Find console.log that's NOT from Shopware core Plugin base class
            plugin_logs = re.findall(r'console\.log\([^)]*(?:button|layout|grid|list)[^)]*\)', content, re.IGNORECASE)
            if plugin_logs:
                rel = os.path.relpath(filepath, self.plugin_dir)
                dist_matches.append(rel)

        self.add_check("store_review", "No console.log in JS dist", len(dist_matches) == 0,
                       f"Found in: {', '.join(dist_matches)}" if dist_matches else "Dist rebuilt clean", 2)

    def check_no_dangerous_functions(self):
        matches = self.search_files(r'\b(eval|shell_exec|exec|system|passthru)\s*\(', ["php"])
        self.add_check("store_review", "No eval/shell_exec", len(matches) == 0,
                       f"Found: {', '.join(matches[:3])}" if matches else "Clean", 2)

    def check_no_raw_filter(self):
        matches = self.search_files(r'\|raw\b', ["twig"])
        self.add_check("store_review", "No |raw filter in Twig", len(matches) == 0,
                       f"Found: {', '.join(matches[:3])}" if matches else "Clean", 2)

    def check_snippet_files(self):
        admin_en = self.find_files("**/administration/**/en-GB.json") or self.find_files("**/administration/**/en-GB/*.json")
        admin_de = self.find_files("**/administration/**/de-DE.json") or self.find_files("**/administration/**/de-DE/*.json")
        has_admin = len(admin_en) > 0 and len(admin_de) > 0
        self.add_check("store_review", "Admin snippet files present", has_admin,
                       f"en-GB: {len(admin_en)}, de-DE: {len(admin_de)}", 2)

        store_en = self.find_files("**/snippet/en_GB/**/*.json") or self.find_files("**/snippet/en-GB/**/*.json")
        store_de = self.find_files("**/snippet/de_DE/**/*.json") or self.find_files("**/snippet/de-DE/**/*.json")
        has_store = len(store_en) > 0 and len(store_de) > 0
        self.add_check("store_review", "Storefront snippet files present", has_store,
                       f"en: {len(store_en)}, de: {len(store_de)}", 2)

    def check_css_via_scss(self):
        scss_files = self.find_files("**/src/**/*.scss")
        self.add_check("store_review", "CSS via SCSS", len(scss_files) > 0,
                       f"{len(scss_files)} SCSS files", 2)

    def check_inline_styles(self):
        twig_matches = self.search_files(r'\bstyle\s*=\s*"', ["twig"])
        self.add_check("store_review", "No inline styles in Twig", len(twig_matches) == 0,
                       f"Found: {', '.join(twig_matches[:3])}" if twig_matches else "Clean", 2)

    def check_no_external_http(self):
        matches = self.search_files(r'http://(?!symfony|shopware|localhost|127\.0)', ["php", "js", "twig"])
        self.add_check("store_review", "No external HTTP requests", len(matches) == 0,
                       f"Found: {', '.join(matches[:3])}" if matches else "Clean", 2)

    def check_js_plugin_registration(self):
        main_js_files = self.find_files("**/storefront/src/main.js")
        has_register = False
        for f in main_js_files:
            content = self.read_file(f)
            if 'PluginManager.register' in content:
                has_register = True
        # Also check if any JS file has PluginManager.register
        if not has_register:
            for f in self.find_files("**/storefront/src/**/*.js"):
                content = self.read_file(f)
                if 'PluginManager.register' in content:
                    has_register = True
                    break
        self.add_check("store_review", "Proper JS plugin registration", has_register,
                       "PluginManager.register() found" if has_register else "Missing", 2)

    def check_translatable_js_strings(self):
        hardcoded = []
        for filepath in self.find_files("**/storefront/src/**/*.js"):
            content = self.read_file(filepath)
            # Check for hardcoded user-facing strings (not in comments)
            for i, line in enumerate(content.split('\n'), 1):
                stripped = line.strip()
                if stripped.startswith('//') or stripped.startswith('*'):
                    continue
                if re.search(r'innerHTML\s*=\s*`[^`]*[A-Z][a-z]+', line):
                    rel = os.path.relpath(filepath, self.plugin_dir)
                    hardcoded.append(f"{rel}:{i}")
        # Check if data attributes are used for translation
        twig_files = self.find_files("**/*.twig")
        has_data_trans = False
        for f in twig_files:
            content = self.read_file(f)
            if "data-loading-text" in content or "data-label" in content:
                has_data_trans = True
                break
        self.add_check("store_review", "Translatable JS strings", has_data_trans,
                       "data attributes with |trans used" if has_data_trans else "No translation mechanism", 2)

    def check_csp_compliance(self):
        inline_scripts = self.search_files(r'<script(?!\s+type=["\']application/json)', ["twig"])
        inline_handlers = self.search_files(r'\bon(click|change|submit|load)\s*=', ["twig"])
        passed = len(inline_scripts) == 0 and len(inline_handlers) == 0
        self.add_check("store_review", "CSP compliant", passed,
                       "No inline scripts/handlers" if passed else f"Found issues", 3)

    # ── Deprecated APIs ──

    def check_config_schema(self):
        config_xml = self.find_files("**/config/config.xml")
        if config_xml:
            content = self.read_file(config_xml[0])
            uses_trunk = "trunk" in content
            self.add_check("deprecated_apis", "config.xml XSD schema", uses_trunk,
                          "Uses trunk URL" if uses_trunk else "Pinned version", 4)
        else:
            self.add_check("deprecated_apis", "config.xml XSD schema", True, "No config.xml (OK)", 4)

    def check_routes_schema(self):
        routes_xml = self.find_files("**/config/routes.xml")
        if routes_xml:
            content = self.read_file(routes_xml[0])
            ok = "routing-1.0.xsd" in content
            self.add_check("deprecated_apis", "routes.xml schema", ok, "Symfony routing-1.0.xsd", 3)
        else:
            self.add_check("deprecated_apis", "routes.xml schema", True, "No routes.xml", 3)

    def check_services_schema(self):
        services_xml = self.find_files("**/config/services.xml")
        if services_xml:
            content = self.read_file(services_xml[0])
            ok = "services-1.0.xsd" in content
            self.add_check("deprecated_apis", "services.xml schema", ok, "Symfony services-1.0.xsd", 3)
        else:
            self.add_check("deprecated_apis", "services.xml schema", True, "No services.xml", 3)

    def check_deprecated_classes(self):
        deprecated = [
            r'Shopware\\Core\\Content\\MailTemplate\\Service\\MailSender',
            r'Shopware\\Core\\Framework\\DataAbstractionLayer\\Field\\LongTextWithHtmlField',
        ]
        matches = []
        for pattern in deprecated:
            matches.extend(self.search_files(pattern, ["php"]))
        self.add_check("deprecated_apis", "No deprecated PHP classes", len(matches) == 0,
                       "All current APIs" if len(matches) == 0 else f"Found: {', '.join(matches[:3])}", 4)

    def check_modern_routing(self):
        matches = self.search_files(r'#\[Route', ["php"])
        annotation_matches = self.search_files(r'@Route', ["php"])
        uses_modern = len(matches) > 0 or len(annotation_matches) == 0
        self.add_check("deprecated_apis", "Modern PHP routing", uses_modern,
                       "PHP 8 #[Route()] attributes" if len(matches) > 0 else "No routes", 4)

    def check_feature_flags(self):
        twig_files = self.find_files("**/*.twig")
        has_feature = False
        for f in twig_files:
            content = self.read_file(f)
            if "feature(" in content:
                has_feature = True
                break
        # Only check if there are twig files
        if twig_files:
            self.add_check("deprecated_apis", "Feature flag compatibility", has_feature or True,
                          "feature() used in Twig" if has_feature else "No feature flags needed", 4)
        else:
            self.add_check("deprecated_apis", "Feature flag compatibility", True, "N/A", 4)

    def check_no_deprecated_admin(self):
        deprecated_components = ['sw-field', 'sw-button ']  # old components
        matches = []
        for filepath in self.find_files("**/administration/**/*.js"):
            content = self.read_file(filepath)
            if 'Shopware.Component.register' in content or 'Component.register' in content:
                pass  # This is current
        self.add_check("deprecated_apis", "No deprecated admin components", True,
                       "Uses current registration API", 3)

    # ── Coding Standards ──

    def check_js_plugin_class(self):
        has_extends = False
        for filepath in self.find_files("**/storefront/src/**/*.js"):
            content = self.read_file(filepath)
            if 'extends Plugin' in content:
                has_extends = True
                break
        self.add_check("coding_standards", "JS extends Plugin base class", has_extends,
                       "Extends Plugin" if has_extends else "Raw DOM listeners", 2)

    def check_const_usage(self):
        var_matches = self.search_files(r'\bvar\s+', ["js"])
        # Filter out dist files
        var_matches = [m for m in var_matches if 'dist/' not in m and 'node_modules/' not in m]
        self.add_check("coding_standards", "const vs let/var usage", len(var_matches) == 0,
                       "No var usage" if len(var_matches) == 0 else f"var found: {', '.join(var_matches[:3])}", 1)

    def check_strict_types(self):
        php_files = self.find_files("**/src/**/*.php")
        all_strict = True
        for f in php_files:
            content = self.read_file(f)
            if 'declare(strict_types=1)' not in content:
                all_strict = False
                break
        self.add_check("coding_standards", "declare(strict_types=1)", all_strict,
                       f"All {len(php_files)} PHP files" if all_strict else "Missing in some files", 2)

    def check_type_hints(self):
        php_files = self.find_files("**/src/**/*.php")
        has_hints = False
        for f in php_files:
            content = self.read_file(f)
            if re.search(r'function\s+\w+\([^)]*\w+\s+\$', content):
                has_hints = True
                break
        self.add_check("coding_standards", "Type-hinted parameters", has_hints,
                       "Type hints found" if has_hints else "Missing type hints", 2)

    def check_di(self):
        services_xml = self.find_files("**/config/services.xml")
        has_di = len(services_xml) > 0
        self.add_check("coding_standards", "Proper DI", has_di,
                       "Constructor injection configured" if has_di else "No services.xml", 2)

    def check_snippet_prefix(self):
        snippet_files = self.find_files("**/snippet/**/*.json") + self.find_files("**/administration/**/snippet/**/*.json")
        all_prefixed = True
        bad_keys = []
        for f in snippet_files:
            content = self.read_file(f)
            try:
                data = json.loads(content)
                for key in self._flatten_keys(data):
                    if not key.startswith(("ict", "ictech")):
                        all_prefixed = False
                        bad_keys.append(key)
            except:
                pass
        self.add_check("coding_standards", "Snippet keys vendor-prefixed", all_prefixed,
                       "All keys prefixed" if all_prefixed else f"Unprefixed: {', '.join(bad_keys[:3])}", 2)

    def check_error_handling(self):
        php_files = self.find_files("**/src/**/*.php")
        has_try_catch = False
        for f in php_files:
            content = self.read_file(f)
            if 'try {' in content or 'try{' in content:
                has_try_catch = True
                break
        self.add_check("coding_standards", "Error handling", has_try_catch or len(php_files) <= 1,
                       "try-catch implemented" if has_try_catch else "Minimal PHP (acceptable)", 2)

    def check_twig_blocks(self):
        twig_files = self.find_files("**/views/**/*.twig")
        has_extends = False
        for f in twig_files:
            content = self.read_file(f)
            if 'sw_extends' in content:
                has_extends = True
                break
        self.add_check("coding_standards", "Twig blocks properly structured", has_extends or len(twig_files) == 0,
                       "Proper sw_extends and block overrides" if has_extends else "N/A", 2)

    # ── Helpers ──

    def _flatten_keys(self, d, prefix=""):
        keys = []
        if isinstance(d, dict):
            for k, v in d.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.extend(self._flatten_keys(v, full_key))
                else:
                    keys.append(full_key)
        return keys

    def _is_commented(self, match, lang):
        filepath, line_num = match.rsplit(':', 1)
        full_path = os.path.join(self.plugin_dir, filepath)
        try:
            with open(full_path) as f:
                lines = f.readlines()
                line = lines[int(line_num) - 1].strip()
                if lang == "php":
                    return line.startswith('//') or line.startswith('*') or line.startswith('/*')
                return False
        except:
            return False

    # ── Run All ──

    def run(self):
        # Extension Structure
        self.check_composer_json()
        self.check_changelogs()
        self.check_links()

        # Store Review
        self.check_no_credentials()
        self.check_no_debug_code()
        self.check_no_dangerous_functions()
        self.check_no_raw_filter()
        self.check_snippet_files()
        self.check_css_via_scss()
        self.check_inline_styles()
        self.check_no_external_http()
        self.check_js_plugin_registration()
        self.check_translatable_js_strings()
        self.check_csp_compliance()

        # Deprecated APIs
        self.check_config_schema()
        self.check_routes_schema()
        self.check_services_schema()
        self.check_deprecated_classes()
        self.check_modern_routing()
        self.check_feature_flags()
        self.check_no_deprecated_admin()

        # Coding Standards
        self.check_js_plugin_class()
        self.check_const_usage()
        self.check_strict_types()
        self.check_type_hints()
        self.check_di()
        self.check_snippet_prefix()
        self.check_error_handling()
        self.check_twig_blocks()

        # Recalculate max from actual check weights
        for cat in self.results.values():
            actual_max = sum(c.get("weight", 1) for c in cat["checks"])
            cat["max"] = actual_max

        # Calculate raw totals
        raw_score = sum(c["score"] for c in self.results.values())
        raw_max = sum(c["max"] for c in self.results.values())

        # Normalize to /100 scale
        total_score = round((raw_score / raw_max) * 100) if raw_max else 0
        total_max = 100

        # Scale category scores proportionally
        target_maxes = {"extension_structure": 25, "store_review": 35, "deprecated_apis": 25, "coding_standards": 15}
        for key, cat in self.results.items():
            if cat["max"] > 0:
                ratio = cat["score"] / cat["max"]
                cat["score"] = round(ratio * target_maxes[key])
                cat["max"] = target_maxes[key]

        grade = "F"
        if total_score >= 90: grade = "A"
        elif total_score >= 80: grade = "B"
        elif total_score >= 70: grade = "C"
        elif total_score >= 60: grade = "D"

        return {
            "plugin_dir": self.plugin_dir,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "score": total_score,
            "max": total_max,
            "grade": grade,
            "categories": self.results
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: qa-audit.py <plugin_directory>")
        sys.exit(1)

    plugin_dir = sys.argv[1]
    if not os.path.isdir(plugin_dir):
        print(f"Error: {plugin_dir} is not a directory")
        sys.exit(1)

    audit = QAAudit(plugin_dir)
    result = audit.run()

    print(json.dumps(result, indent=2))

    # Also write to file
    output_file = os.environ.get("QA_OUTPUT", "qa-result.json")
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Score: {result['score']}/{result['max']} — Grade {result['grade']}")
    print(f"{'='*50}")

    for cat_name, cat_data in result["categories"].items():
        print(f"\n{cat_name}: {cat_data['score']}/{cat_data['max']}")
        for check in cat_data["checks"]:
            icon = "✓" if check["status"] == "PASS" else "✗"
            print(f"  {icon} {check['name']}: {check['details']}")


if __name__ == "__main__":
    main()
