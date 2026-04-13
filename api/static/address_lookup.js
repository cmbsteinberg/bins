const ADDRESS_API_URL = "https://www.midsuffolk.gov.uk/api/jsonws/invoke";

const ADDRESS_HEADERS = {
	accept: "*/*",
	"content-type": "text/plain;charset=UTF-8",
};

function titleCase(str) {
	return str.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatAddress(item) {
	const parts = [
		item.addressLine1,
		item.addressLine2,
		item.addressLine3,
		item.addressLine4,
		item.city,
	]
		.filter(Boolean)
		.map(titleCase);
	parts.push(item.postcode);
	return parts.join(", ");
}

class AddressLookup {
	constructor({ timeout = 15000 } = {}) {
		this._timeout = timeout;
	}

	async searchAddresses(postcode) {
		postcode = postcode.trim().toUpperCase();

		const body =
			`{"/placecube_digitalplace.addresscontext/search-address-by-postcode":` +
			`{"companyId":"1486681","postcode":"${postcode}","fallbackToNationalLookup":false}}`;

		const resp = await fetch(ADDRESS_API_URL, {
			method: "POST",
			headers: ADDRESS_HEADERS,
			body,
			signal: AbortSignal.timeout(this._timeout),
		});

		if (!resp.ok) {
			throw new Error(`Address lookup failed (${resp.status})`);
		}

		const data = await resp.json();

		return data.map((item) => ({
			uprn: item.UPRN,
			full_address: formatAddress(item),
			postcode: item.postcode,
		}));
	}
}

export { AddressLookup };
