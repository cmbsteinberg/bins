const ADDRESS_API_URL = "https://www.midsuffolk.gov.uk/api/jsonws/invoke";

const ADDRESS_HEADERS = {
	accept: "*/*",
	"content-type": "text/plain;charset=UTF-8",
	"x-csrf-token": "Ba9vI91W",
};

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
			full_address: item.fullAddress,
			postcode: item.postcode,
		}));
	}
}

export { AddressLookup };
