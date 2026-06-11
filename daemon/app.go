package main

import (
	"bytes"
	"context"
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	stdruntime "runtime"
	"time"

	"os"
	"path/filepath"
	"strings"

	"github.com/emersion/go-autostart"
	"github.com/wailsapp/wails/v2/pkg/runtime"
	"golang.design/x/hotkey"
)

type Config struct {
	HotkeyMod    string `json:"hotkey_mod"`
	HotkeyKey    string `json:"hotkey_key"`
	GeminiAPIKey string `json:"gemini_api_key"`
}

var currentHotkey *hotkey.Hotkey
var autostartApp *autostart.App
var configFilePath string

//go:embed icon.png
var neoIcon []byte

// App struct
type App struct {
	ctx       context.Context
	isVisible bool
	config    Config
}

func getConfigPath() string {
	homeDir, _ := os.UserHomeDir()
	return filepath.Join(homeDir, ".neo-daemon.json")
}

func loadConfig() Config {
	c := Config{
		HotkeyMod: "Mod1",
		HotkeyKey: "Space",
	}
	data, err := os.ReadFile(getConfigPath())
	if err == nil {
		json.Unmarshal(data, &c)
	}
	return c
}

func saveConfig(c Config) {
	data, _ := json.MarshalIndent(c, "", "  ")
	os.WriteFile(getConfigPath(), data, 0644)
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{
		isVisible: false,
		config:    loadConfig(),
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx

	execPath, _ := os.Executable()
	autostartApp = &autostart.App{
		Name:        "neo-daemon",
		DisplayName: "Neo Daemon",
		Exec:        []string{execPath},
	}

	if stdruntime.GOOS == "linux" {
		a.setupLinuxDesktopEntry(execPath)
	}

	go a.listenHotkeyLoop()
}

func (a *App) ShowWindow() {
	if a.ctx != nil {
		runtime.WindowShow(a.ctx)
	}
}

// ShowChat shows the main window and hides settings
func (a *App) ShowChat() {
	if a.ctx != nil {
		runtime.WindowShow(a.ctx)
		a.isVisible = true
		runtime.EventsEmit(a.ctx, "show-chat")
	}
}

// ShowSettings shows the main window and shows settings
func (a *App) ShowSettings() {
	if a.ctx != nil {
		runtime.WindowShow(a.ctx)
		a.isVisible = true
		runtime.EventsEmit(a.ctx, "open-settings")
	}
}

func (a *App) setupLinuxDesktopEntry(execPath string) {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return
	}
	appDir := filepath.Join(homeDir, ".local", "share", "applications")
	iconDir := filepath.Join(homeDir, ".local", "share", "icons")
	desktopPath := filepath.Join(appDir, "neo.desktop")
	iconPath := filepath.Join(iconDir, "neo.png")

	os.MkdirAll(appDir, 0755)
	os.MkdirAll(iconDir, 0755)

	os.WriteFile(iconPath, neoIcon, 0644)

	desktopContent := fmt.Sprintf(`[Desktop Entry]
Name=Neo
Comment=Assistente Pessoal Neo
Exec=%s
Icon=%s
Terminal=false
Type=Application
Categories=Utility;
`, execPath, iconPath)
	os.WriteFile(desktopPath, []byte(desktopContent), 0644)
}

func parseModifier(m string) hotkey.Modifier {
	switch strings.ToLower(m) {
	case "mod1", "alt":
		return hotkey.Mod1
	case "ctrl", "control":
		return hotkey.ModCtrl
	case "shift":
		return hotkey.ModShift
	case "mod4", "super", "win":
		return hotkey.Mod4
	default:
		return hotkey.Mod1 // Default to Alt
	}
}

func parseKey(k string) hotkey.Key {
	switch strings.ToLower(k) {
	case "space":
		return hotkey.KeySpace
	case "enter", "return":
		return hotkey.KeyReturn
	default:
		// Attempt to map A-Z
		if len(k) == 1 {
			char := strings.ToUpper(k)[0]
			if char >= 'A' && char <= 'Z' {
				return hotkey.Key(hotkey.KeyA + hotkey.Key(char-'A'))
			}
		}
		return hotkey.KeySpace
	}
}

func (a *App) registerHotkey() {
	if currentHotkey != nil {
		currentHotkey.Unregister()
	}

	mod := parseModifier(a.config.HotkeyMod)
	key := parseKey(a.config.HotkeyKey)

	currentHotkey = hotkey.New([]hotkey.Modifier{mod}, key)
	err := currentHotkey.Register()
	if err != nil {
		fmt.Printf("hotkey: failed to register: %v\n", err)
	}
}

func (a *App) listenHotkeyLoop() {
	a.registerHotkey()

	for {
		hk := currentHotkey
		if hk == nil {
			time.Sleep(500 * time.Millisecond)
			continue
		}

		_, ok := <-hk.Keydown()
		if !ok {
			time.Sleep(100 * time.Millisecond)
			continue
		}

		if hk == currentHotkey {
			if a.isVisible {
				runtime.WindowHide(a.ctx)
				a.isVisible = false
			} else {
				runtime.WindowShow(a.ctx)
				runtime.EventsEmit(a.ctx, "focus-input")
				a.isVisible = true
			}
		}
	}
}

// GetCurrentHotkey returns the currently saved hotkey
func (a *App) GetCurrentHotkey() string {
	return a.config.HotkeyMod + " + " + a.config.HotkeyKey
}

// GetGeminiAPIKey returns the saved Gemini API Key
func (a *App) GetGeminiAPIKey() string {
	return a.config.GeminiAPIKey
}

// SetGeminiAPIKey saves the Gemini API Key from frontend
func (a *App) SetGeminiAPIKey(key string) bool {
	a.config.GeminiAPIKey = strings.TrimSpace(key)
	saveConfig(a.config)
	return true
}

// SetHotkey updates the hotkey from frontend
func (a *App) SetHotkey(mod string, key string) bool {
	if currentHotkey != nil {
		currentHotkey.Unregister()
	}

	m := parseModifier(mod)
	k := parseKey(key)

	newHotkey := hotkey.New([]hotkey.Modifier{m}, k)
	err := newHotkey.Register()
	if err != nil {
		fmt.Printf("SetHotkey failed: %v\n", err)
		a.registerHotkey() // fallback to previous
		return false
	}

	currentHotkey = newHotkey
	a.config.HotkeyMod = mod
	a.config.HotkeyKey = key
	saveConfig(a.config)
	return true
}

// GetAutoStartStatus checks if the daemon starts on boot
func (a *App) GetAutoStartStatus() bool {
	return autostartApp.IsEnabled()
}

// ToggleAutoStart enables or disables starting on boot
func (a *App) ToggleAutoStart(enable bool) string {
	var err error
	if enable {
		err = autostartApp.Enable()
	} else {
		err = autostartApp.Disable()
	}
	if err != nil {
		return err.Error()
	}
	return "OK"
}

type ChatRequest struct {
	Message string `json:"message"`
}

type ChatResponse struct {
	Response string `json:"response"`
}

// WhatsAppStatusResponse represents the status of the WhatsApp bridge
type WhatsAppStatusResponse struct {
	Connected bool   `json:"connected"`
	QR        string `json:"qr"`
}

func getInternalAPIKey() string {
	execPath, err := os.Executable()
	if err != nil {
		return ""
	}
	dir := filepath.Dir(execPath)
	for i := 0; i < 4; i++ {
		envPath := filepath.Join(dir, ".env")
		if data, err := os.ReadFile(envPath); err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				if strings.HasPrefix(line, "INTERNAL_API_KEY=") {
					return strings.TrimSpace(strings.TrimPrefix(line, "INTERNAL_API_KEY="))
				}
			}
		}
		dir = filepath.Dir(dir)
	}
	return ""
}

// AskNeo sends a message to the Neo Python backend
func (a *App) AskNeo(message string) string {
	payload, err := json.Marshal(ChatRequest{Message: message})
	if err != nil {
		return fmt.Sprintf("Erro interno: %v", err)
	}

	client := &http.Client{Timeout: 30 * time.Second}
	req, err := http.NewRequest("POST", "http://127.0.0.1:5000/chat", bytes.NewBuffer(payload))
	if err != nil {
		return fmt.Sprintf("Erro ao conectar com Neo: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Neo-Token", getInternalAPIKey())
	if a.config.GeminiAPIKey != "" {
		req.Header.Set("X-Gemini-API-Key", a.config.GeminiAPIKey)
	}

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Sprintf("Erro do cliente: %v", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Sprintf("Erro ao ler resposta: %v", err)
	}

	if resp.StatusCode != http.StatusOK {
		var errData map[string]interface{}
		if err := json.Unmarshal(body, &errData); err == nil {
			if detail, ok := errData["detail"].(string); ok {
				return fmt.Sprintf("Erro do Neo (HTTP %d): %s", resp.StatusCode, detail)
			}
		}
		return fmt.Sprintf("Erro do Neo (HTTP %d): %s", resp.StatusCode, string(body))
	}

	var chatResp ChatResponse
	err = json.Unmarshal(body, &chatResp)
	if err != nil {
		return fmt.Sprintf("Erro no formato da resposta: %s", string(body))
	}

	return chatResp.Response
}

// GetWhatsAppStatus checks the connection status and QR code from the Node bridge
func (a *App) GetWhatsAppStatus() WhatsAppStatusResponse {
	var status WhatsAppStatusResponse
	client := &http.Client{Timeout: 5 * time.Second}
	req, err := http.NewRequest("GET", "http://127.0.0.1:3303/status", nil)
	if err != nil {
		return status
	}
	req.Header.Set("X-Neo-Token", getInternalAPIKey())

	resp, err := client.Do(req)
	if err != nil {
		return status
	}
	defer resp.Body.Close()

	if resp.StatusCode == 200 {
		json.NewDecoder(resp.Body).Decode(&status)
	}
	return status
}

// HideWindow allows frontend to hide the window
func (a *App) HideWindow() {
	runtime.WindowHide(a.ctx)
	a.isVisible = false
}

// Quit application
func (a *App) Quit() {
	runtime.Quit(a.ctx)
}

// CheckSingleInstance ensures only one instance of the daemon runs and shows the chat window on new launches
func (a *App) CheckSingleInstance() {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return
	}
	socketPath := filepath.Join(homeDir, ".neo-daemon.sock")

	// Try to connect to see if an instance is actually listening
	conn, err := net.Dial("unix", socketPath)
	if err == nil {
		// An instance is running and listening! Send show and exit.
		conn.Write([]byte("show"))
		conn.Close()
		os.Exit(0)
	}

	// No instance is listening. Remove any stale socket file and listen.
	os.Remove(socketPath)
	listener, err := net.Listen("unix", socketPath)
	if err != nil {
		return
	}

	// Handle incoming messages to show the window
	go func() {
		defer listener.Close()
		defer os.Remove(socketPath)
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			buf := make([]byte, 10)
			n, _ := conn.Read(buf)
			if n > 0 && string(buf[:n]) == "show" {
				a.ShowChat()
			}
			conn.Close()
		}
	}()
}

type GeminiInlineData struct {
	MimeType string `json:"mimeType"`
	Data     string `json:"data"`
}

type GeminiPart struct {
	InlineData *GeminiInlineData `json:"inlineData,omitempty"`
	Text       string            `json:"text,omitempty"`
}

type GeminiContent struct {
	Parts []GeminiPart `json:"parts"`
}

type GeminiRequest struct {
	Contents []GeminiContent `json:"contents"`
}

type GeminiResponsePart struct {
	Text string `json:"text"`
}

type GeminiResponseContent struct {
	Parts []GeminiResponsePart `json:"parts"`
}

type GeminiResponseCandidate struct {
	Content GeminiResponseContent `json:"content"`
}

type GeminiResponse struct {
	Candidates []GeminiResponseCandidate `json:"candidates"`
}

// TranscribeAudio calls Gemini API to transcribe recorded voice commands
func (a *App) TranscribeAudio(base64Data string, mimeType string) string {
	apiKey := a.config.GeminiAPIKey
	if apiKey == "" {
		// Try to read from system .env if not set in config
		apiKey = os.Getenv("GEMINI_API_KEY")
	}
	if apiKey == "" {
		return "Erro: GEMINI_API_KEY não configurada. Por favor, adicione sua chave nas Configurações."
	}

	// Clean mimeType (remove codecs metadata, e.g. "audio/webm;codecs=opus" -> "audio/webm")
	cleanMimeType := strings.Split(mimeType, ";")[0]
	cleanMimeType = strings.TrimSpace(cleanMimeType)

	reqPayload := GeminiRequest{
		Contents: []GeminiContent{
			{
				Parts: []GeminiPart{
					{
						InlineData: &GeminiInlineData{
							MimeType: cleanMimeType,
							Data:     base64Data,
						},
					},
					{
						Text: "Por favor, transcreva o áudio desta mensagem em português e retorne APENAS o texto da transcrição literal de forma limpa, sem comentários ou explicações.",
					},
				},
			},
		},
	}

	payloadBytes, err := json.Marshal(reqPayload)
	if err != nil {
		return fmt.Sprintf("Erro interno ao serializar áudio: %v", err)
	}

	apiURL := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=%s", apiKey)
	
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Post(apiURL, "application/json", bytes.NewBuffer(payloadBytes))
	if err != nil {
		return fmt.Sprintf("Erro ao conectar com API do Gemini: %v", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Sprintf("Erro ao ler resposta de transcrição: %v", err)
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Sprintf("Erro da API Gemini (HTTP %d): %s", resp.StatusCode, string(bodyBytes))
	}

	var geminiResp GeminiResponse
	err = json.Unmarshal(bodyBytes, &geminiResp)
	if err != nil {
		return fmt.Sprintf("Erro ao decodificar resposta de transcrição: %v", err)
	}

	if len(geminiResp.Candidates) == 0 || len(geminiResp.Candidates[0].Content.Parts) == 0 {
		return "Erro: Nenhuma transcrição gerada pelo Gemini."
	}

	return strings.TrimSpace(geminiResp.Candidates[0].Content.Parts[0].Text)
}

