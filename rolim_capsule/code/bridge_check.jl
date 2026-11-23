#=
KOPRU DOGRULAMA (Julia tarafi): .nbin'i run_one.jl'nin GERCEK parser'i ile okur ve
parmak-izi basar. Python tarafi ayni parmak-izini JSON'dan hesaplar -> eslesmeli.
NOKTA-DEGERLER kritik: toplamlar transpoza duyarsizdir, transpoz hatasini yakalamaz.
Kullanim: julia bridge_check.jl <instance.nbin>
=#
include("run_one.jl")   # PROGRAM_FILE guard'i sayesinde main() tetiklenmez

n, m, p, S, rdy, Mel = parse_niche_bin(ARGS[1])

sum_p = sum(Int64, p)
sum_S = sum(Int64(sum(Int64, S[l])) for l in 1:m)
sum_r = sum(Int64, rdy)
sum_e = sum(Int64(sum(Mel[j])) for j in 1:n)

# nokta-degerler (transpoz/indeks hatasini yakalar): asimetrik indeksler secildi
i1 = min(2, m); j1 = min(5, n)
i2 = min(3, n); j2 = min(7, n)
l2 = min(2, m)
println("BRIDGE n=$n m=$m sump=$sum_p sumS=$sum_S sumr=$sum_r sume=$sum_e " *
        "p_$(i1)_$(j1)=$(p[i1, j1]) S_$(l2)_$(i2)_$(j2)=$(S[l2][i2, j2]) " *
        "e_$(j1)_$(i1)=$(Mel[j1][i1]) r_$(i1)=$(rdy[i1])")
