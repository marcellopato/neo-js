export namespace main {
	
	export class WhatsAppStatusResponse {
	    connected: boolean;
	    qr: string;
	
	    static createFrom(source: any = {}) {
	        return new WhatsAppStatusResponse(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.connected = source["connected"];
	        this.qr = source["qr"];
	    }
	}

}

