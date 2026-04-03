import { AddressLookup } from "/static/address_lookup.js";

const API = "/api/v1";
const addressLookup = new AddressLookup();
let currentData = null;

const $ = (sel) => document.querySelector(sel);

function show(id) {
	$(`#${id}`).classList.remove("hidden");
}
function hide(id) {
	$(`#${id}`).classList.add("hidden");
}
function showError(msg) {
	$("#error").textContent = msg;
	show("error");
}
function clearError() {
	hide("error");
}

$("#postcode-form").addEventListener("submit", async (e) => {
	e.preventDefault();
	clearError();
	hide("results");
	const postcode = $("#postcode").value.trim();
	if (!postcode) return;

	const btn = e.target.querySelector("button");
	btn.setAttribute("aria-busy", "true");

	try {
		// Address search (client-side) and council lookup (server-side) in parallel
		const [addresses, councilResp] = await Promise.all([
			addressLookup.searchAddresses(postcode),
			fetch(`${API}/council/${encodeURIComponent(postcode)}`),
		]);

		let council_id = null;
		let council_name = null;
		if (councilResp.ok) {
			const councilData = await councilResp.json();
			council_id = councilData.council_id;
			council_name = councilData.council_name;
		}

		currentData = { addresses, council_id, council_name };

		if (addresses.length === 0) {
			showError("No addresses found for that postcode.");
			return;
		}

		const select = $("#address-select");
		select.innerHTML = '<option value="">-- Choose address --</option>';
		addresses.forEach((addr, i) => {
			const opt = document.createElement("option");
			opt.value = i;
			opt.textContent = addr.full_address;
			select.appendChild(opt);
		});

		hide("step-postcode");
		show("step-address");
	} catch (err) {
		showError(err.message);
	} finally {
		btn.removeAttribute("aria-busy");
	}
});

$("#address-select").addEventListener("change", (e) => {
	$("#address-btn").disabled = !e.target.value;
});

$("#back-btn").addEventListener("click", () => {
	hide("step-address");
	hide("results");
	show("step-postcode");
});

$("#address-btn").addEventListener("click", async () => {
	clearError();
	hide("results");
	const idx = $("#address-select").value;
	if (!idx || !currentData) return;

	const addr = currentData.addresses[idx];
	const councilId = currentData.council_id;

	if (!councilId) {
		showError(
			"Could not determine council for this postcode. Council may not be supported yet.",
		);
		return;
	}

	const btn = $("#address-btn");
	btn.setAttribute("aria-busy", "true");

	try {
		const params = new URLSearchParams({
			council: councilId,
			postcode: addr.postcode,
		});
		const resp = await fetch(
			`${API}/lookup/${encodeURIComponent(addr.uprn)}?${params}`,
		);
		if (!resp.ok) {
			const err = await resp.json().catch(() => ({}));
			throw new Error(err.detail || `Lookup failed (${resp.status})`);
		}
		const data = await resp.json();
		renderResults(addr, data);
	} catch (err) {
		showError(err.message);
	} finally {
		btn.removeAttribute("aria-busy");
	}
});

const BIN_SVG = `<svg viewBox="0 0 64 80" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="12" y="18" width="40" height="54" rx="3" fill="#546E7A" stroke="#37474F" stroke-width="2"/>
  <rect x="16" y="24" width="4" height="40" rx="1" fill="#455A64"/>
  <rect x="24" y="24" width="4" height="40" rx="1" fill="#455A64"/>
  <rect x="36" y="24" width="4" height="40" rx="1" fill="#455A64"/>
  <rect x="44" y="24" width="4" height="40" rx="1" fill="#455A64"/>
  <rect x="8" y="12" width="48" height="8" rx="2" fill="#607D8B" stroke="#37474F" stroke-width="2"/>
  <rect x="24" y="6" width="16" height="8" rx="2" fill="#78909C" stroke="#37474F" stroke-width="2"/>
  <rect x="14" y="72" width="10" height="4" rx="2" fill="#37474F"/>
  <rect x="40" y="72" width="10" height="4" rx="2" fill="#37474F"/>
</svg>`;

function formatDate(dateStr) {
	const d = new Date(dateStr + "T00:00:00");
	return d.toLocaleDateString("en-GB", {
		weekday: "long",
		day: "numeric",
		month: "long",
		year: "numeric",
	});
}

function relativeDay(dateStr) {
	const today = new Date();
	today.setHours(0, 0, 0, 0);
	const d = new Date(dateStr + "T00:00:00");
	const diff = Math.round((d - today) / 86400000);
	if (diff < 0)
		return { text: `${-diff} day${diff === -1 ? "" : "s"} ago`, past: true };
	if (diff === 0) return { text: "Today", past: false };
	if (diff === 1) return { text: "Tomorrow", past: false };
	return { text: `In ${diff} days`, past: false };
}

function renderResults(addr, data) {
	const section = $("#results");
	const council = currentData.council_name || data.council;
	const councilId = currentData.council_id;

	if (data.collections.length === 0) {
		section.innerHTML = `
            <article>
                <header><strong>${addr.full_address}</strong></header>
                <p>No upcoming collections found.</p>
            </article>`;
		show("results");
		return;
	}

	// Group collections by type, preserving date order
	const groups = new Map();
	for (const c of data.collections) {
		if (!groups.has(c.type)) groups.set(c.type, []);
		groups.get(c.type).push(c);
	}

	let cards = "";
	for (const [type, items] of groups) {
		const next = items[0];
		const rel = relativeDay(next.date);
		const future = items.slice(1);

		let moreHtml = "";
		if (future.length > 0) {
			const lis = future.map((c) => `<li>${formatDate(c.date)}</li>`).join("");
			moreHtml = `
				<details class="bin-more">
					<summary>${future.length} more date${future.length === 1 ? "" : "s"}</summary>
					<ul>${lis}</ul>
				</details>`;
		}

		cards += `
			<div class="bin-group">
				<div class="bin-next">
					<div class="bin-icon">${BIN_SVG}</div>
					<div class="bin-info">
						<p class="bin-type">${type}</p>
						<p class="bin-date">${formatDate(next.date)}</p>
						<span class="bin-relative${rel.past ? " past" : ""}">${rel.text}</span>
					</div>
				</div>
				${moreHtml}
			</div>`;
	}

	const calParams = new URLSearchParams({
		council: councilId,
		postcode: addr.postcode,
	});
	const calUrl = `${API}/calendar/${encodeURIComponent(addr.uprn)}?${calParams}`;

	section.innerHTML = `
        <article>
            <header>
                <strong>${addr.full_address}</strong>
                <div class="collection-date">${council}</div>
            </header>
            ${cards}
            <footer>
                <a href="${calUrl}" role="button" class="outline">Subscribe to calendar (.ics)</a>
            </footer>
        </article>`;
	show("results");
}
