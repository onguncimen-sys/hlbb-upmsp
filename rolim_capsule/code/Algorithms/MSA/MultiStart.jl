#=
* Implementation of the Multi-Start Algorithm (MSA) of Avalos-Rolsales et al.
* The International Journal of Advanced Manufacturing Technology 76 (2015) 1705–1718
* Problem: Unrelated parallel machine scheduling with sequence-dependent setup times
* Objective: Makespan
* Coded by Gustavo Alencar Rolim - Universidade de São Paulo (2022/2023)
=#

function MachineSpan(M::Int8, p::Matrix{Int16}, S::Vector{Matrix{Int16}},
    sol::Vector{Vector{Int16}})
    #----- Calculates the span of a given machine 

    Ct::Int32 = 0
    size::Int16 = length(sol[M])

    for i::Int16 in 1:size
        if i != size
            Ct += p[M, sol[M][i]] + S[M][sol[M][i], sol[M][i+1]]
        else
            Ct += p[M, sol[M][i]]
        end
    end
    
    return(Ct)
end

function AvgProc(m::Int8, n::Int16, p::Matrix{Int16})
    #----- Returns a sorted list according to the average processing times

    AVG = zeros(Float16, n)

    for j::Int16 in 1:n
        AVG[j] = sum(p[:, j])
        AVG[j] /= m
    end

    U::Vector{Int16} = sortperm(AVG, rev = true) 
    
    return(U)
end

function InsCost(sol::Vector{Vector{Int16}}, M::Int8, J::Int16, PI::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, O::Vector{Int32})
    #----- Calculates the difference on the maximum completion time after inserting a job in a machine

    Cb = O[M] # Cost before insertion in machine M
    Ca = Cb # Cost after insertion in machine M
    SM::Int16 = length(sol[M]) # Length of the machine to be inserted

    if SM >= 1
        if PI == 1 
            Ca += p[M, J] + S[M][J, sol[M][PI]]
        elseif PI == SM+1
            Ca += S[M][sol[M][PI-1], J] + p[M, J]
        else
            Ca += S[M][sol[M][PI-1], J] + p[M, J] + S[M][J, sol[M][PI]]
        end
    else
        Ca += p[M, J]
    end

    Delta::Int32 = Ca - Cb

    return(Delta)
end

function Constructive(m::Int8, n::Int16, sol::Vector{Vector{Int16}},
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, O::Vector{Int32}, alpha::Int16)
    #----- GRASP construction phase 

    U = AvgProc(m, n, p)
    BPos = zeros(Int32, m)
    BDelta = zeros(Int32, m)
    Eval = zeros(Int32, m)
    size = n
    NI::Int64 = 0 
    
    while size != 0
        pos::Int16 = rand(1:alpha)
        J::Int16 = U[pos]

        for i::Int8 in 1:m
            last::Int16 = length(sol[i])+1
            Big::Int32 = 999999999

            for j::Int16 in 1:last
                Delta::Int32 = InsCost(sol, i, J, j, p, S, O)
                NI += 1

                if Delta < Big 
                    Big = Delta 
                    BDelta[i] = Delta
                    BPos[i] = j 
                end
            end
        end

        Eval .+= O
        Eval .+= BDelta
        M::Int8 = argmin(Eval)
        O[M] += BDelta[M]
        insert!(sol[M], BPos[M], J)
        deleteat!(U, pos)
        size -= 1

        if alpha > size
            alpha = size
        end

        Eval .= 0 
        BPos .= 0 
        BDelta .= 0
    end

    return(NI)
end

function DeltaIns(sol::Vector{Vector{Int16}}, O::Vector{Int32}, MR::Int8, MI::Int8,
    PR::Int16, PI::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Fast calculation of the machine span in the insertion neighborhood

    Cbi::Int32 = O[MR] # Cost before insertion on machine i (job removal)
    Cbj::Int32 = O[MI] # Cost before insertion on machine j (job insertion)
    Cai::Int32 = Cbi # Cost after insertion on machine i (job removal)
    Caj::Int32 = Cbj # Cost after insertion on machine j (job insertion)
    J::Int16 = sol[MR][PR] # Job to be removed and then inserted
    SR::Int16 = length(sol[MR]) # Length of the busiest machine 
    SI::Int16 = length(sol[MI]) # Length of the machine with a lower span

    #----- Calculates the new span after job removal on the busiest machine
    
    if SR > 1
        if PR == 1
            Cai -= p[MR, J] + S[MR][J, sol[MR][PR+1]]
        elseif PR == SR
            Cai -= S[MR][sol[MR][PR-1], J] + p[MR, J]
        else
            Cai -= S[MR][sol[MR][PR-1], J] + p[MR, J] + S[MR][J, sol[MR][PR+1]]
            Cai += S[MR][sol[MR][PR-1], sol[MR][PR+1]]
        end
    else
        Cai -= p[MR, J]
    end

    #----- Calculates the new span after job insertion on the machine with a lower span

    if SI >= 1
        if PI == 1
            Caj += p[MI, J] + S[MI][J, sol[MI][1]]
        elseif PI == SI+1
            Caj += S[MI][sol[MI][PI-1], J] + p[MI, J]
        else
            Caj += S[MI][sol[MI][PI-1], J] + p[MI, J] + S[MI][J, sol[MI][PI]]
        end
    else
        Caj += p[MI, J]
    end

    #----- Evaluates the move

    Value::Int32 = max(Cbi, Cbj) - max(Cai, Caj)
    
    return(Value)
end

function ExecuteIns(sol::Vector{Vector{Int16}}, O::Vector{Int32}, MR::Int8, MI::Int8,
    PR::Int16, PI::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the insertion movement

    JOB::Int16 = sol[MR][PR]
    deleteat!(sol[MR], PR)
    insert!(sol[MI], PI, JOB)

    #----- Updates the spans

    O[MR] = MachineSpan(MR, p, S, sol)
    O[MI] = MachineSpan(MI, p, S, sol)
end

function Insertion(sol::Vector{Vector{Int16}}, O::Vector{Int32}, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, Lm::Vector{Int8})
    #----- Insertion neighborhood

    count::Int8 = 1
    eval::Int64 = 0

    while count <= m
        MR::Int8 = Lm[count]
        best_mov::Int32 = 0
        BMR::Int8 = 0 
        BMI::Int8 = 0
        PI::Int16 = 0 
        PR::Int16 = 0 

        for i::Int8 in 1:m
            if i != Lm[count]
                MI::Int8 = i
                
                for j::Int16 in eachindex(sol[MR])
                    for k::Int16 in eachindex(sol[MI])
                        value_mov::Int32 = DeltaIns(sol, O, MR, MI, j, k, p, S)
                        eval += 1

                        if value_mov > 0 && value_mov > best_mov
                            best_mov = value_mov
                            BMR = MR 
                            BMI = MI
                            PR = j 
                            PI = k
                        end
                    end
                end
            end
        end

        if best_mov != 0 
            ExecuteIns(sol, O, BMR, BMI, PR, PI, p, S)
            Lm = sortperm(O, rev = true)
            count = 1
        else 
            count += 1
        end
    end

    return(eval)
end

function DeltaSwap(sol::Vector{Vector{Int16}}, O::Vector{Int32}, M1::Int8, M2::Int8,
    S1::Int16, S2::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Fast calculation of the machine span in the swap neighborhood
    Cbi::Int32 = O[M1] # Cost before swap of machine i 
    Cbj::Int32 = O[M2] # Cost before swap of machine j 
    Cai::Int32 = Cbi # Cost after swap of machine i 
    Caj::Int32 = Cbj # Cost after swap of machine j
    J1::Int16 = sol[M1][S1] # Job to swap on the busiest machine
    J2::Int16 = sol[M2][S2] # Job to swap on the less busy machine
    SR::Int16 = length(sol[M1]) # Length of the busiest machine 
    SI::Int16 = length(sol[M2]) # Length of the machine with a lower span

    #----- Calculates the new span after the job swap on the busiest machine

    if SR > 1
        if S1 == 1
            Cai -= p[M1, J1] + S[M1][J1, sol[M1][S1+1]]
            Cai += p[M1, J2] + S[M1][J2, sol[M1][S1+1]]
        elseif S1 == SR
            Cai -= S[M1][sol[M1][S1-1], J1] + p[M1, J1] 
            Cai += S[M1][sol[M1][S1-1], J2] + p[M1, J2]
        else
            Cai -= S[M1][sol[M1][S1-1], J1] + p[M1, J1] + S[M1][J1, sol[M1][S1+1]]
            Cai += S[M1][sol[M1][S1-1], J2] + p[M1, J2] + S[M1][J2, sol[M1][S1+1]]
        end
    else
        Cai -= p[M1, J1]
        Cai += p[M1, J2]
    end

    #----- Calculates the new span after the job swap on the less busy machine

    if SI > 1
        if S2 == 1
            Caj -= p[M2, J2] + S[M2][J2, sol[M2][S2+1]]
            Caj += p[M2, J1] + S[M2][J1, sol[M2][S2+1]]
        elseif S2 == SI
            Caj -= S[M2][sol[M2][S2-1], J2] + p[M2, J2]
            Caj += S[M2][sol[M2][S2-1], J1] + p[M2, J1]
        else
            Caj -= S[M2][sol[M2][S2-1], J2] + p[M2, J2] + S[M2][J2, sol[M2][S2+1]]
            Caj += S[M2][sol[M2][S2-1], J1] + p[M2, J1] + S[M2][J1, sol[M2][S2+1]]
        end
    else
        Caj -= p[M2, J2]
        Caj += p[M2, J1]
    end

    #----- Evaluates the move

    Value::Int32 = max(Cbi, Cbj) - max(Cai, Caj)

    return(Value)
end

function ExecuteSwap(sol::Vector{Vector{Int16}}, O::Vector{Int32}, M1::Int8, M2::Int8, S1::Int16, S2::Int16,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the swap movement

    J1::Int16 = sol[M1][S1]
    J2::Int16 = sol[M2][S2]
    sol[M1][S1] = J2
    sol[M2][S2] = J1

    #----- Updates the spans

    O[M1] = MachineSpan(M1, p, S, sol)
    O[M2] = MachineSpan(M2, p, S, sol)
end

function Swap(sol::Vector{Vector{Int16}}, O::Vector{Int32}, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, Lm::Vector{Int8})
    #----- Swap neighborhood

    count::Int8 = 1
    eval::Int64 = 0

    while count <= m
        M1::Int8 = Lm[count] # Index of the busiest machine
        M::Int8 = 0 # Machine to swap the jobs
        S1::Int16 = 0 # Best position of the job on the busiest machine
        S2::Int16 = 0 # Best position of the job on the less busy machine 
        best_mov::Int32 = 0 # Best movement 

        for i::Int8 in 1:m
            if i != Lm[count]
                M2::Int8 = i
                
                for j::Int16 in eachindex(sol[M1])
                    for k::Int16 in eachindex(sol[M2])
                        value_mov::Int32 = DeltaSwap(sol, O, M1, M2, j, k, p, S)
                        eval += 1

                        if value_mov > 0 && value_mov > best_mov
                            best_mov = value_mov
                            S1 = j 
                            S2 = k
                            M = M2
                        end
                    end
                end
            end
        end

        if best_mov != 0
            ExecuteSwap(sol, O, M1, M, S1, S2, p, S)
            Lm = sortperm(O, rev = true)
            count = 1
        else 
            count += 1
        end
    end

    return(eval)
end

function DeltaN(sol::Vector{Vector{Int16}}, O::Vector{Int32}, M::Int8, P1::Int16, P2::Int16,
    size::Int16, S::Vector{Matrix{Int16}})
    #----- Fast calculation of the machine span in the nearest neighborhood

    C::Int32 = O[M] # Cost before reinsertion 
    J::Int16 = sol[M][P1] # Job to be reinserted

    #----- Remove the setup from the current position 

    if P1 == 1
        C -= S[M][J, sol[M][P1+1]]
    elseif P1 == size
        C -= S[M][sol[M][P1-1], J]
    else
        C -= S[M][sol[M][P1-1], J] + S[M][J, sol[M][P1+1]]
        C += S[M][sol[M][P1-1], sol[M][P1+1]]
    end

    #----- Add the new setup costs

    if P2 == 1
        C += S[M][J, sol[M][P2]]
    elseif P2 == size
        C += S[M][sol[M][P2], J]
    else
        if P1 > P2
            C -= S[M][sol[M][P2-1], sol[M][P2]]
            C += S[M][sol[M][P2-1], J] + S[M][J, sol[M][P2]]
        else
            C -= S[M][sol[M][P2], sol[M][P2+1]]
            C += S[M][sol[M][P2], J] + S[M][J, sol[M][P2+1]]
        end
    end

    Value::Int32 =  O[M] - C
    
    return(Value)
end

function ExecuteReins(sol::Vector{Vector{Int16}}, O::Vector{Int32}, MR::Int8,
    P1::Int16, P2::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the reinsertion movement

    J::Int16 = sol[MR][P1]
    deleteat!(sol[MR], P1)
    insert!(sol[MR], P2, J)

    #----- Updates the spans

    O[MR] = MachineSpan(MR, p, S, sol)
end

function OptimizeSetup(sol::Vector{Vector{Int16}}, O::Vector{Int32}, Mj::Int8,
    POS::Int16, size::Int16, p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Optimize the setup times in a sequence
    
    best_mov::Int32 = 0 # Best movement
    Bpos::Int16 = 0 # Saves the best position
    eval::Int64 = 0 

    for i::Int16 in 1:size
        if i != POS
            value_mov = DeltaN(sol, O, Mj, POS, i, size, S)
            eval += 1

            if value_mov > 0 && value_mov > best_mov
                best_mov = value_mov
                Bpos = i
            end
        end
    end
    
    if best_mov != 0 
        ExecuteReins(sol, O, Mj, POS, Bpos, p, S)
    end

    return(eval)
end

function OrOpt(sol::Vector{Vector{Int16}}, O::Vector{Int32}, M::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Execute the optimization of setups in each individual machine 

    SM::Int16 = length(sol[M])
    eval::Int64 = 0

    if SM > 1
        for j::Int16 in eachindex(sol[M])
            eval += OptimizeSetup(sol, O, M, j, SM, p, S)
        end
    end

    return(eval)
end

function StageI(m::Int8, sol::Vector{Vector{Int16}}, O::Vector{Int32},
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the first stage VND
    
    Lm::Vector{Int8} = sortperm(O, rev = true)
    iprv::Bool = true
    Cmax::Int32 = maximum(O)
    eval::Int64 = 0 

    while iprv == true 
        #----- Insertion neighborhood
        
        eval += Insertion(sol, O, m, p, S, Lm)

        #----- Swap neighborhood (Interchange neighborhood)

        eval += Swap(sol, O, m, p, S, Lm)

        #----- Optimize the setups in each machine
    
        for i::Int8 in 1:m 
            eval += OrOpt(sol, O, i, p, S)
        end

        Inc::Int32 = maximum(O)

        #----- Tracks the solution improvement

        if Inc < Cmax
            Cmax = Inc 
            iprv = true 
        else
            iprv = false
        end
    end

    return(eval)
end

function ComInsertion(sol::Vector{Vector{Int16}}, O::Vector{Int32}, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, Lm::Vector{Int8})
    #----- Executes the composite insertion neighborhood

    count::Int8 = 1
    eval::Int64 = 0 

    while count <= m
        MR::Int8 = Lm[count]
        best_mov::Int32 = 0
        BMR::Int8 = 0 # Best machine to remove the job 
        BMI::Int8 = 0 # Best machine to insert the job
        PI::Int16 = 0 # Insertion position 
        PR::Int16 = 0 # Removal position 

        for i::Int8 in 1:m
            if i != Lm[count]
                MI::Int8 = i
                
                for j::Int16 in eachindex(sol[MR])
                    for k::Int16 in eachindex(sol[MI])
                        value_mov::Int32 = DeltaIns(sol, O, MR, MI, j, k, p, S)
                        eval += 1
                        
                        if value_mov > 0 && value_mov > best_mov
                            best_mov = value_mov
                            BMR = MR 
                            BMI = MI
                            PR = j 
                            PI = k
                        end
                    end
                end
            end
        end

        if best_mov != 0 
            ExecuteIns(sol, O, BMR, BMI, PR, PI, p, S)

            #----- Executes the Or-Opt in both machines 

            eval += OrOpt(sol, O, BMR, p, S)
            eval += OrOpt(sol, O, BMI, p, S)

            #----- Update the machine list and the counter

            Lm = sortperm(O, rev = true)
            count = 1
        else 
            count += 1
        end
    end

    return(eval)
end

function ComSwap(sol::Vector{Vector{Int16}}, O::Vector{Int32}, m::Int8,
    p::Matrix{Int16}, S::Vector{Matrix{Int16}}, Lm::Vector{Int8})
    #----- Executes the composite swap neighborhood

    count::Int8 = 1
    eval::Int64 = 0

    while count <= m
        M1::Int8 = Lm[count] # Index of the busiest machine
        M::Int8 = 0 # Machine to swap the jobs
        S1::Int16 = 0 # Best position of the job on the busiest machine
        S2::Int16 = 0 # Best position of the job on the less busy machine 
        best_mov::Int32 = 0 # Best movement 

        for i::Int8 in 1:m
            if i != Lm[count]
                M2::Int8 = i
                
                for j::Int16 in eachindex(sol[M1])
                    for k::Int16 in eachindex(sol[M2])
                        value_mov::Int32 = DeltaSwap(sol, O, M1, M2, j, k, p, S)
                        eval += 1

                        if value_mov > 0 && value_mov > best_mov
                            best_mov = value_mov
                            S1 = j 
                            S2 = k
                            M = M2
                        end
                    end
                end
            end
        end

        if best_mov != 0
            ExecuteSwap(sol, O, M1, M, S1, S2, p, S)

            #----- Executes the Or-Opt in both machines 

            eval += OrOpt(sol, O, M1, p, S)
            eval += OrOpt(sol, O, M, p, S)
            
            #----- Update the machine list and the counter

            Lm = sortperm(O, rev = true)
            count = 1
        else 
            count += 1
        end
    end

    return(eval)
end

function StageII(m::Int8, sol::Vector{Vector{Int16}}, O::Vector{Int32},
    p::Matrix{Int16}, S::Vector{Matrix{Int16}})
    #----- Executes the second stage VND

    Lm::Vector{Int8} = sortperm(O, rev = true)
    iprv::Bool = true
    Cmax::Int32 = maximum(O)
    eval::Int64 = 0 

    while iprv == true 
        #----- Composite insertion neighborhood

        eval += ComInsertion(sol, O, m, p, S, Lm)

        #----- Composite swap (interchange) neighborhood

        eval += ComSwap(sol, O, m, p, S, Lm)

        Inc::Int32 = maximum(O)

        #----- Tracks the solution improvement

        if Inc < Cmax 
            Cmax = Inc 
            iprv = true 
        else
            iprv = false 
        end
    end

    return(eval)
end

function ResetSolution(sol::Vector{Vector{Int16}}, O::Vector{Int32}, m::Int8)
    #----- Resets the current solution to zero 

    for i::Int8 in 1:m
        size = length(sol[i])

        while size != 0 
            popfirst!(sol[i])
            size -= 1
        end
    end

    O .= 0
end

function Main_MSA(m::Int8, n::Int16, p::Matrix{Int16},
    S::Vector{Matrix{Int16}}, t::Int)
    #----- Definition of parameters

    alpha::Int16 = ceil(n/3)
    NI::Int64 = 0 
    I::Int64 = 0

    #----- Time variables

    Tmax::Float64 = convert(Float64, n) * convert(Float64, m) * convert(Float64, t)/2000
    elapsed::Float64 = 0
    ST::Float64 = time()
    tbest::Float64 = 0.0   # en iyiyi bulma ani (sn)

    #----- Definition of the solution and objective function

    sol = Vector{Int16}[[] for i in 1:m]
    O = zeros(Int32, m)
    
    B::Int32 = 999999999

    while elapsed <= Tmax
        #----- Semigreedy phase 

        NI += Constructive(m, n, sol, p, S, O, alpha)

        #----- Stage I

        NI += StageI(m, sol, O, p, S)

        #----- Stage II

        NI += StageII(m, sol, O, p, S)

        #----- Acceptance criterion 

        Inc::Int32 = maximum(O)

        if Inc < B
            B = Inc
            tbest = time() - ST
        end

        ResetSolution(sol, O, m)

        I += 1
        elapsed = time() - ST
    end

    return(B, I, NI, tbest)
end