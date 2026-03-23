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

	const rows = data.collections
		.map((c) => {
			const d = new Date(c.date);
			const dateStr = d.toLocaleDateString("en-GB", {
				weekday: "long",
				day: "numeric",
				month: "long",
				year: "numeric",
			});
			const icon = c.icon || "";
			return `<div class="collection">
            <span class="collection-icon">${icon}</span>
            <div>
                <strong>${c.type}</strong>
                <div class="collection-date">${dateStr}</div>
            </div>
        </div>`;
		})
		.join("");

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
            ${rows}
            <footer>
                <a href="${calUrl}" role="button" class="outline">Subscribe to calendar (.ics)</a>
            </footer>
        </article>`;
	show("results");
}
