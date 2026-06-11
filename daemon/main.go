package main

import (
	"context"
	"embed"
	_ "image/jpeg"
	_ "image/png"
	"os"

	"fyne.io/systray"
	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/mac"
)

//go:embed all:frontend/dist
var assets embed.FS

//go:embed build/trayicon.png
var iconData []byte

func main() {
	app := NewApp()
	app.CheckSingleInstance()

	// Inicia o Systray em background antes do Wails
	go systray.Run(func() {
		systray.SetIcon(iconData)
		systray.SetTitle("Neo")
		systray.SetTooltip("Neo AI Assistant")

		mOpen := systray.AddMenuItem("Chat", "Abre a janela de chat")
		mSettings := systray.AddMenuItem("Configurações", "Abre o painel de configurações")
		systray.AddSeparator()
		mQuit := systray.AddMenuItem("Fechar o Neo", "Encerrar o aplicativo")

		go func() {
			for {
				select {
				case <-mOpen.ClickedCh:
					app.ShowChat()
				case <-mSettings.ClickedCh:
					app.ShowSettings()
				case <-mQuit.ClickedCh:
					systray.Quit()
					os.Exit(0)
				}
			}
		}()
	}, func() {})

	err := wails.Run(&options.App{
		Title:            "Neo",
		Width:            700,
		Height:           500,
		Frameless:        true,
		AlwaysOnTop:      true,
		StartHidden:      true,
		CSSDragProperty:  "--wails-draggable",
		CSSDragValue:     "drag",
		BackgroundColour: &options.RGBA{R: 0, G: 0, B: 0, A: 0},
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		OnStartup: func(ctx context.Context) {
			app.startup(ctx)
		},
		Bind: []interface{}{
			app,
		},
		Mac: &mac.Options{
			TitleBar: &mac.TitleBar{
				TitlebarAppearsTransparent: true,
				HideTitle:                  true,
				HideTitleBar:               true,
				FullSizeContent:            true,
				UseToolbar:                 false,
				HideToolbarSeparator:       true,
			},
			WebviewIsTransparent: true,
			WindowIsTranslucent:  true,
		},
	})

	if err != nil {
		println("Error:", err.Error())
	}
}
